from __future__ import annotations

import shutil
import subprocess


class CommandResult:
    def __init__(self, command: list[str], found: bool, returncode: int | None, stdout: str, stderr: str) -> None:
        self.command = command
        self.found = found
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def as_dict(self) -> dict:
        return {
            "command": self.command,
            "found": self.found,
            "returncode": self.returncode,
            "stdout": self.stdout[-8000:],
            "stderr": self.stderr[-4000:],
        }


def run_command(command: list[str], timeout: int = 120) -> CommandResult:
    if not shutil.which(command[0]):
        return CommandResult(command, False, None, "", f"{command[0]} not installed")

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(command, True, completed.returncode, completed.stdout, completed.stderr)

