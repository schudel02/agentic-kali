from __future__ import annotations

from agentic_kali.policy.models import Action


def request_manual_approval(action: Action) -> bool:
    print(f"Approve action: {action.name} -> {action.target}")
    return input("Type APPROVE to continue: ").strip() == "APPROVE"


def request_bulk_approval(actions: list[Action]) -> bool:
    print("The following actions require approval:")
    for action in actions:
        print(f"  {action.name} -> {action.target}")
    return input("Type APPROVE to run all: ").strip() == "APPROVE"

