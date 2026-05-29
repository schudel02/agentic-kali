from __future__ import annotations

from agentic_kali.evidence.store import EvidenceStore
from agentic_kali.policy.models import Scope


def build_report(scope: Scope, evidence: EvidenceStore) -> dict:
    return {
        "engagement": scope.engagement_name,
        "targets": scope.targets,
        "scope": {
            "targets": scope.targets,
            "allowed_actions": scope.allowed_actions,
            "testing_goal": scope.testing_goal,
            "restrictions": scope.restrictions,
            "intrusive_allowed": scope.intrusive_allowed,
            "public_targets_allowed": scope.public_targets_allowed,
        },
        "approval_mode": scope.approval_mode,
        "findings": evidence.findings,
        "events": evidence.events,
    }

