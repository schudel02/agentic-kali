from __future__ import annotations

from agentic_kali.desktop.controller import DesktopController
from agentic_kali.policy.models import Scope


class WatchMode:
    def __init__(self, scope: Scope) -> None:
        self.scope = scope
        self.desktop = DesktopController()

    def dry_plan(self, command: str) -> list[str]:
        return [
            "open terminal",
            f"type scoped command for: {command}",
            "wait for output",
            "record activity",
        ]

    def can_run(self) -> bool:
        return self.scope.signed_permission and self.desktop.available()

