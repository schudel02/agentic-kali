from __future__ import annotations

import json
from pathlib import Path

from agentic_kali.core.planner import SAFE_RECON_ACTIONS
from agentic_kali.policy.models import ApprovalMode, Scope


def run_scope_wizard(output_path: Path) -> Scope:
    print("Authorized testing scope wizard")
    engagement = _ask("Engagement name", "local-lab")
    targets = _ask("Targets, comma-separated", "127.0.0.1")
    actions = _ask("Actions, comma-separated", ",".join(SAFE_RECON_ACTIONS))
    approval = _ask("Approval mode [recon_only|approval_required|lab_only]", "recon_only")
    public_targets_allowed = _ask("Allow public internet targets? [no|yes]", "no") == "yes"

    scope = Scope(
        engagement_name=engagement,
        targets=[item.strip() for item in targets.split(",") if item.strip()],
        allowed_actions=[item.strip() for item in actions.split(",") if item.strip()],
        approval_mode=ApprovalMode(approval),
        intrusive_allowed=False,
        signed_permission=_ask("Type AUTHORIZED to confirm permission", "") == "AUTHORIZED",
        public_targets_allowed=public_targets_allowed,
    )

    output_path.write_text(json.dumps(scope.model_dump(mode="json"), indent=2), encoding="utf-8")
    return scope


def _ask(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default
