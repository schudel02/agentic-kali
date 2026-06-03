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
        from agentic_kali.ai.provider import APIKeyError

        session_done = [
            e["data"].get("action")
            for e in self.evidence.events
            if e["event"] == "action.started"
        ]

        # Skip Claude if keywords already give a clear answer — saves a full API call
        keyword_names = actions_from_command(self.command, self.scope.allowed_actions, session_done)
        if self._command_is_unambiguous():
            ai_names = []
            selected = keyword_names
        else:
            try:
                ai_names = AIProvider().suggest_actions(self._prompt())
            except APIKeyError as exc:
                self.evidence.log("ai.key_error", {"provider": exc.provider, "code": exc.code, "detail": exc.detail})
                ai_names = []
            selected = ai_names or keyword_names
        all_known = set(ALL_ADMIN_ACTIONS)
        allowed_names = [
            name
            for name in selected
            if name in self.scope.allowed_actions and name in all_known
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

    def _command_is_unambiguous(self) -> bool:
        """Return True when keyword matching gives a confident answer — no Claude needed."""
        from agentic_kali.ai.commands import KEYWORDS, ALL_PHRASES, AUTO_PHRASES
        text = self.command.lower()
        # Explicit tool keyword, 'run all', or 'auto' → skip Claude
        if any(phrase in text for phrase in ALL_PHRASES + AUTO_PHRASES):
            return True
        if any(kw in text for kws in KEYWORDS.values() for kw in kws):
            return True
        # No command at all → rule-based fallback is fine
        if not self.command.strip():
            return True
        return False

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
        # Keep only the last 8 completed actions — older ones add tokens without value
        session_completed = [
            e["data"].get("action")
            for e in self.evidence.events
            if e["event"] == "action.started"
        ][-8:]

        # Truncate findings to the 5 most severe, title+severity only — no long evidence text
        findings = sorted(
            self.evidence.findings,
            key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(f.get("severity", "info"), 4),
        )[:5]
        findings_summary = [f"{f['severity']}:{f['title'][:60]}" for f in findings]

        prior_completed = self._prior_completed()[:8]  # cap prior history too

        # Scope allowed actions — only send names not titles (shorter)
        allowed = [a for a in self.scope.allowed_actions if a in set(ALL_ADMIN_ACTIONS)]

        return (
            f"cmd:{self.command or 'none'} "
            f"allowed:{','.join(allowed)} "
            f"intrusive:{self.scope.intrusive_allowed} "
            f"done_session:{','.join(session_completed) or 'none'} "
            f"done_prior:{','.join(prior_completed) or 'none'} "
            f"findings:{';'.join(findings_summary) or 'none'} "
            "Pick actions from allowed list not already done. "
            "Intrusive only if intrusive=True. "
            "Return JSON only."
        )
