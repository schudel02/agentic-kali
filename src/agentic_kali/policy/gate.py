from __future__ import annotations

from agentic_kali.policy.models import Action, PolicyDecision, Scope
from agentic_kali.policy.targets import is_public_target


class PolicyGate:
    def __init__(self, scope: Scope, admin_mode: bool = False) -> None:
        self.scope = scope
        self.admin_mode = admin_mode

    def evaluate(self, action: Action) -> PolicyDecision:
        if self.admin_mode:
            return PolicyDecision(
                action=action.name,
                target=action.target,
                allowed=True,
                reason="admin mode: all guardrails bypassed",
            )

        if not self.scope.signed_permission:
            return self._deny(action, "explicit permission not confirmed")

        if action.target not in self.scope.targets:
            return self._deny(action, "target outside scope")

        if is_public_target(action.target) and not self.scope.public_targets_allowed:
            return self._deny(action, "public target requires explicit public_targets_allowed")

        if action.name not in self.scope.allowed_actions:
            return self._deny(action, "action not allowed")

        if action.intrusive and not self.scope.intrusive_allowed:
            return self._deny(action, "intrusive action requires approval")

        if self.scope.approval_mode == "approval_required":
            return PolicyDecision(
                action=action.name,
                target=action.target,
                allowed=False,
                approval_required=True,
                reason="manual approval required",
            )

        return PolicyDecision(
            action=action.name,
            target=action.target,
            allowed=True,
            reason="allowed by scope",
        )

    @staticmethod
    def _deny(action: Action, reason: str) -> PolicyDecision:
        return PolicyDecision(
            action=action.name,
            target=action.target,
            allowed=False,
            approval_required=False,
            reason=reason,
        )
