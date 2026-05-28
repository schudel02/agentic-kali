from __future__ import annotations

from agentic_kali.core.planner import ALL_ACTIONS, INTRUSIVE_ACTIONS
from agentic_kali.ai.provider import AIProvider
from agentic_kali.ai.commands import actions_from_command
from agentic_kali.evidence.store import EvidenceStore
from agentic_kali.policy.models import Action, Scope


class AIPlanner:
    def __init__(self, scope: Scope, evidence: EvidenceStore, command: str = "") -> None:
        self.scope = scope
        self.evidence = evidence
        self.command = command

    def propose_next_actions(self) -> list[Action]:
        ai_names = AIProvider().suggest_actions(self._prompt())
        selected = ai_names or actions_from_command(self.command, self.scope.allowed_actions)
        allowed_names = [
            name
            for name in selected
            if name in ALL_ACTIONS and name in self.scope.allowed_actions
        ]

        proposed: list[Action] = []
        for target in self.scope.targets:
            for name in allowed_names:
                proposed.append(Action(name=name, target=target, intrusive=name in INTRUSIVE_ACTIONS))

        self.evidence.log(
            "ai.plan.proposed",
            {
                "mode": "authorized-scoped-testing",
                "ai_requested": ai_names,
                "actions": [action.model_dump() for action in proposed],
            },
        )
        return proposed

    def _prompt(self) -> str:
        return (
            "Return only JSON like {\"actions\":[\"ping_check\"]}. "
            f"Known actions: {', '.join(ALL_ACTIONS)}. "
            f"Scope allowed actions: {', '.join(self.scope.allowed_actions)}. "
            f"Intrusive allowed: {self.scope.intrusive_allowed}. "
            f"User command: {self.command}. "
            "Choose only actions allowed by scope. Use intrusive actions only when intrusive_allowed is true and the request calls for them."
        )
