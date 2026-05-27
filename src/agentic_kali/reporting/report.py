from __future__ import annotations

from agentic_kali.evidence.store import EvidenceStore
from agentic_kali.policy.models import Scope


def build_report(scope: Scope, evidence: EvidenceStore) -> dict:
    return {
        "engagement": scope.engagement_name,
        "targets": scope.targets,
        "approval_mode": scope.approval_mode,
        "findings": evidence.findings,
        "events": evidence.events,
    }

