from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass


ALIASES = {
    "social engineering toolkit": "setoolkit",
    "set": "setoolkit",
    "metasploit": "msfconsole",
    "burp": "burpsuite",
    "burp suite": "burpsuite",
    "wireshark": "wireshark",
    "terminal": "qterminal",
    "firefox": "firefox",
}

HIGH_RISK = {"setoolkit", "msfconsole", "hydra", "sqlmap"}


@dataclass(frozen=True)
class LaunchRequest:
    display_name: str
    command: str
    risk: str


def parse_launch_request(text: str) -> LaunchRequest | None:
    lowered = text.lower().strip()
    match = re.search(r"\b(?:open|launch|start)\s+(.+)$", lowered)
    if not match:
        return None

    requested = match.group(1).strip().strip(".?!")
    command = ALIASES.get(requested, requested.split()[0])
    command = re.sub(r"[^a-zA-Z0-9._+-]", "", command)
    if not command:
        return None

    risk = "approval_required" if command in HIGH_RISK else "normal"
    return LaunchRequest(display_name=requested, command=command, risk=risk)


def launch_program(command: str) -> tuple[bool, str]:
    resolved = shutil.which(command)
    if not resolved:
        return False, f"{command} is not installed or not on PATH."
    subprocess.Popen([resolved])
    return True, f"Opened {command}."

