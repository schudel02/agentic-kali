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
    ) -> None:
        self.scope = scope
        self.command = command
        self.policy = PolicyGate(scope)
        self.evidence = EvidenceStore(on_event=on_event)
        self.tools = ToolRegistry(self.evidence)

    def run(self) -> dict:
        self.evidence.log("run.started", {"time": datetime.now(UTC).isoformat()})

        planned_actions = AIPlanner(self.scope, self.evidence, command=self.command).propose_next_actions()

        for action in planned_actions:
            decision = self.policy.evaluate(action)
            self.evidence.log("policy.decision", decision.model_dump())
            if decision.approval_required and request_manual_approval(action):
                self.evidence.log("approval.manual", {"action": action.name, "target": action.target})
                self.tools.run(action)
                continue
            if decision.allowed:
                self.tools.run(action)

        report = build_report(self.scope, self.evidence)
        self.evidence.log("run.completed", {"findings": len(report["findings"])})
        return report
