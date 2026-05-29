from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ApprovalMode(StrEnum):
    RECON_ONLY = "recon_only"
    APPROVAL_REQUIRED = "approval_required"
    LAB_ONLY = "lab_only"


class Scope(BaseModel):
    engagement_name: str
    targets: list[str] = Field(min_length=1)
    allowed_actions: list[str] = Field(default_factory=lambda: ["ping_check"])
    approval_mode: ApprovalMode = ApprovalMode.RECON_ONLY
    intrusive_allowed: bool = False
    signed_permission: bool = False
    public_targets_allowed: bool = False
    testing_goal: str = ""
    restrictions: str = ""


class Action(BaseModel):
    name: str
    target: str
    intrusive: bool = False


class PolicyDecision(BaseModel):
    action: str
    target: str
    allowed: bool
    approval_required: bool = False
    reason: str
