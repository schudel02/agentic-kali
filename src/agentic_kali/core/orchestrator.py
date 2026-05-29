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
    ) -> None:
        self.scope = scope
        self.command = command
        self.should_stop = should_stop or (lambda: False)
        self.policy = PolicyGate(scope, admin_mode=admin_mode)
        self.evidence = EvidenceStore(on_event=on_event)
        self.tools = ToolRegistry(self.evidence, should_stop=self.should_stop)
        self.autonomous = autonomous

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

    def _run_autonomous_loop(self, max_rounds: int = 8) -> None:
        ran: set[tuple[str, str]] = set()
        for round_num in range(max_rounds):
            if self.should_stop():
                self.evidence.log("run.stopped", {"reason": "operator requested stop"})
                break

            planner = AIPlanner(self.scope, self.evidence, command=self.command)
            actions = planner.propose_next_actions()
            new_actions = [a for a in actions if (a.name, a.target) not in ran]

            if not new_actions:
                # Fall back to rule-based next action from findings
                new_actions = self._rule_based_next(ran)

            if not new_actions:
                self.evidence.log("run.autonomous.complete", {"rounds": round_num + 1, "reason": "no new actions"})
                break

            self.evidence.log("run.autonomous.round", {"round": round_num + 1, "actions": [a.name for a in new_actions]})
            self._execute_actions(new_actions)
            for a in new_actions:
                ran.add((a.name, a.target))

    def _rule_based_next(self, ran: set[tuple[str, str]]) -> list:
        from agentic_kali.policy.models import Action
        from agentic_kali.policy.security_settings import INTRUSIVE_ACTIONS

        suggestions: list[str] = []
        allowed = set(self.scope.allowed_actions)

        for finding in self.evidence.findings:
            metadata = finding.get("metadata", {})
            target = finding.get("target", "")

            open_ports = [p["port"] for p in metadata.get("open_ports", []) if p.get("state") == "open"]
            web_ports = {80, 443, 8080, 8443, 8000, 8888}
            if any(p in web_ports for p in open_ports):
                suggestions += ["whatweb", "httpx_probe", "nuclei_safe", "gobuster_dir", "nikto_scan"]

            if metadata.get("technologies"):
                suggestions += ["nuclei_safe", "nuclei_full", "gobuster_dir"]

            if metadata.get("responses"):
                suggestions += ["nuclei_safe", "ffuf_fuzz", "nikto_scan"]

        proposed = []
        seen: set[str] = set()
        for name in suggestions:
            if name in seen or name not in allowed:
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
