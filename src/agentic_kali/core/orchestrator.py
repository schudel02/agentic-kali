from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from agentic_kali.evidence.store import EvidenceStore
from agentic_kali.policy.approval import request_manual_approval
from agentic_kali.policy.gate import PolicyGate
from agentic_kali.ai.planner import AIPlanner
from agentic_kali.policy.models import Scope
from agentic_kali.reporting.report import build_report
from agentic_kali.tools.registry import ToolRegistry


class Orchestrator:
    def __init__(
        self,
        scope: Scope,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        command: str = "",
        should_stop: Callable[[], bool] | None = None,
        admin_mode: bool = False,
        autonomous: bool = False,
        goal: str = "",
    ) -> None:
        self.scope = scope
        self.command = command
        self.should_stop = should_stop or (lambda: False)
        self.policy = PolicyGate(scope, admin_mode=admin_mode)
        self.evidence = EvidenceStore(on_event=on_event)
        self.tools = ToolRegistry(self.evidence, should_stop=self.should_stop)
        self.autonomous = autonomous
        self.goal = goal

    def run(self) -> dict:
        self.evidence.log("run.started", {"time": datetime.now(UTC).isoformat()})

        if self.autonomous:
            self._run_autonomous_loop()
        else:
            planned_actions = AIPlanner(self.scope, self.evidence, command=self.command).propose_next_actions()
            self._execute_actions(planned_actions)

        report = build_report(self.scope, self.evidence)
        self.evidence.log("run.completed", {"findings": len(report["findings"])})
        return report

    def _starting_actions_for_goal(self) -> list[str]:
        g = self.goal.lower()
        allowed = set(self.scope.allowed_actions)
        if "recon" in g:
            return [a for a in ["ping_check", "nmap_top_ports", "whatweb", "httpx_probe"] if a in allowed]
        if "web" in g or "audit" in g:
            return [a for a in ["whatweb", "httpx_probe", "nuclei_safe", "nikto_scan", "gobuster_dir"] if a in allowed]
        if "vuln" in g or "vulnerability" in g:
            return [a for a in ["nuclei_safe", "nuclei_full", "nikto_scan"] if a in allowed]
        if "full" in g or "pentest" in g or "all" in g:
            return [a for a in self.scope.allowed_actions if a in set(self.scope.allowed_actions)]
        # Default: start with recon
        return [a for a in ["ping_check", "nmap_top_ports", "whatweb", "httpx_probe"] if a in allowed]

    def _run_autonomous_loop(self, max_rounds: int = 12) -> None:
        from agentic_kali.policy.models import Action
        from agentic_kali.policy.security_settings import INTRUSIVE_ACTIONS

        ran: set[tuple[str, str]] = set()

        # Seed with goal-specific starting actions
        if self.goal:
            start_names = self._starting_actions_for_goal()
            seed = [
                Action(name=n, target=t, intrusive=n in INTRUSIVE_ACTIONS)
                for t in self.scope.targets
                for n in start_names
                if (n, t) not in ran
            ]
            if seed:
                self.evidence.log("run.autonomous.round", {"round": 0, "actions": [a.name for a in seed], "goal": self.goal})
                self._execute_actions(seed)
                for a in seed:
                    ran.add((a.name, a.target))

        for round_num in range(max_rounds):
            if self.should_stop():
                self.evidence.log("run.stopped", {"reason": "operator requested stop"})
                break

            # Rule-based next actions from findings
            next_actions = self._rule_based_next(ran)

            # Fall back to planner if no rule-based suggestions
            if not next_actions:
                planner = AIPlanner(self.scope, self.evidence, command=self.command)
                proposed = planner.propose_next_actions()
                next_actions = [a for a in proposed if (a.name, a.target) not in ran]

            if not next_actions:
                self.evidence.log("run.autonomous.complete", {"rounds": round_num + 1, "reason": "no new actions"})
                break

            self.evidence.log("run.autonomous.round", {"round": round_num + 1, "actions": [a.name for a in next_actions]})
            self._execute_actions(next_actions)
            for a in next_actions:
                ran.add((a.name, a.target))

    def _rule_based_next(self, ran: set[tuple[str, str]]) -> list:
        from agentic_kali.policy.models import Action
        from agentic_kali.policy.security_settings import INTRUSIVE_ACTIONS

        suggestions: list[str] = []
        allowed = set(self.scope.allowed_actions)
        ran_names = {name for name, _ in ran}

        for finding in self.evidence.findings:
            metadata = finding.get("metadata", {})

            open_ports = [p["port"] for p in metadata.get("open_ports", []) if p.get("state") == "open"]
            web_ports = {80, 443, 8080, 8443, 8000, 8888, 3000, 5000, 8081}
            ssh_ports = {22}
            db_ports = {3306, 5432, 1433, 27017, 6379}

            if any(p in web_ports for p in open_ports):
                suggestions += ["whatweb", "httpx_probe", "nuclei_safe", "nuclei_full", "gobuster_dir", "nikto_scan", "ffuf_fuzz"]
            if any(p in ssh_ports for p in open_ports):
                suggestions += ["hydra_brute"]
            if any(p in db_ports for p in open_ports):
                suggestions += ["sqlmap_safe", "nuclei_full"]
            if metadata.get("technologies"):
                suggestions += ["nuclei_safe", "nuclei_full", "gobuster_dir", "ffuf_fuzz"]
            if metadata.get("responses"):
                suggestions += ["nuclei_safe", "gobuster_dir", "nikto_scan"]

        proposed = []
        seen: set[str] = set()
        for name in suggestions:
            if name in seen or name not in allowed or name in ran_names:
                continue
            seen.add(name)
            for target in self.scope.targets:
                if (name, target) not in ran:
                    proposed.append(Action(name=name, target=target, intrusive=name in INTRUSIVE_ACTIONS))
        return proposed

    def _execute_actions(self, actions: list) -> None:
        for action in actions:
            if self.should_stop():
                self.evidence.log("run.stopped", {"reason": "operator requested stop"})
                break
            decision = self.policy.evaluate(action)
            self.evidence.log("policy.decision", decision.model_dump())
            if decision.approval_required and request_manual_approval(action):
                self.evidence.log("approval.manual", {"action": action.name, "target": action.target})
                self.evidence.log("action.started", {"action": action.name, "target": action.target})
                self.tools.run(action)
                continue
            if decision.allowed:
                self.evidence.log("action.started", {"action": action.name, "target": action.target})
                self.tools.run(action)
