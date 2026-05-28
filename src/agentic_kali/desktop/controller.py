from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class DesktopResult:
    action: str
    ok: bool
    output: str


class DesktopController:
    def available(self) -> bool:
        return all(shutil.which(name) for name in ("xdotool", "wmctrl"))

    def launch_terminal(self) -> DesktopResult:
        return self._run(["xdg-terminal-exec"])

    def launch_browser(self, url: str = "about:blank") -> DesktopResult:
        return self._run(["xdg-open", url])

    def type_text(self, text: str) -> DesktopResult:
        return self._run(["xdotool", "type", "--delay", "15", text])

    def press_enter(self) -> DesktopResult:
        return self._run(["xdotool", "key", "Return"])

    def list_windows(self) -> DesktopResult:
        return self._run(["wmctrl", "-l"])

    def _run(self, command: list[str]) -> DesktopResult:
        if not shutil.which(command[0]):
            return DesktopResult(command[0], False, f"{command[0]} not installed")
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
        return DesktopResult(" ".join(command), completed.returncode == 0, completed.stdout or completed.stderr)

