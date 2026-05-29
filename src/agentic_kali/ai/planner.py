from __future__ import annotations

from agentic_kali.policy.security_settings import ALL_ACTIONS, ALL_ADMIN_ACTIONS, INTRUSIVE_ACTIONS
from agentic_kali.ai.provider import AIProvider
from agentic_kali.ai.commands import actions_from_command
from agentic_kali.evidence.store import EvidenceStore
from agentic_kali.policy.models import Action, Scope
from agentic_kali.reporting.history import read_history


class AIPlanner:
    def __init__(self, scope: Scope, evidence: EvidenceStore, command: str = "") -> None:
        self.scope = scope
        self.evidence = evidence
        self.command = command

    def propose_next_actions(self) -> list[Action]:
        ai_names = AIProvider().suggest_actions(self._prompt())
        selected = ai_names or actions_from_command(
            self.command, self.scope.allowed_actions, self._prior_completed()
        )
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

    def _prior_completed(self) -> list[str]:
        """Action names completed in prior runs against the same targets."""
        targets = set(self.scope.targets)
        completed: list[str] = []
        for run in read_history():
            if set(run.get("targets", [])) & targets:
                for entry in run.get("completed_actions", []):
                    action_name = entry.split(" on ")[0]
                    if action_name not in completed:
                        completed.append(action_name)
        return completed

    def _prompt(self) -> str:
        session_completed = [
            f"{e['data'].get('action')} on {e['data'].get('target')}"
            for e in self.evidence.events
            if e["event"] == "action.started"
        ]
        findings_summary = [
            {"title": f["title"], "severity": f["severity"], "target": f["target"]}
            for f in self.evidence.findings
        ]
        prior_completed = self._prior_completed()
        known = ALL_ADMIN_ACTIONS if any(a not in ALL_ACTIONS for a in self.scope.allowed_actions) else ALL_ACTIONS

        return (
            "Return only JSON like {\"actions\":[\"ping_check\"]}. "
            f"Known actions: {', '.join(known)}. "
            f"Scope allowed actions: {', '.join(self.scope.allowed_actions)}. "
            f"Intrusive allowed: {self.scope.intrusive_allowed}. "
            f"User command: {self.command}. "
            f"Already completed this session: {session_completed or 'none'}. "
            f"Completed in prior runs: {prior_completed or 'none'}. "
            f"Findings so far: {findings_summary or 'none'}. "
            "Choose only actions allowed by scope. "
            "Avoid repeating actions already completed in this or prior runs unless new findings justify it. "
            "Prioritize actions that build on existing findings or explore areas not yet tested. "
            "Use intrusive actions only when intrusive_allowed is true and the request calls for them."
        )
