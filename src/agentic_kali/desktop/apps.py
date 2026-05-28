from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass

URL_RE = re.compile(r"\b((?:https?://)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?)\b")

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
    args: tuple[str, ...] = ()


def parse_launch_request(text: str) -> LaunchRequest | None:
    lowered = text.lower().strip()
    match = re.search(r"\b(?:open|launch|start)\s+(.+)$", lowered)
    if not match:
        return None

    requested = match.group(1).strip().strip(".?!")
    command = ALIASES.get(requested, requested.split()[0])
    url = _extract_url(requested)
    if requested.startswith("firefox") and url:
        command = "firefox"
    command = re.sub(r"[^a-zA-Z0-9._+-]", "", command)
    if not command:
        return None

    risk = "approval_required" if command in HIGH_RISK else "normal"
    args = (_normalize_url(url),) if command in {"firefox", "xdg-open"} and url else ()
    return LaunchRequest(display_name=requested, command=command, risk=risk, args=args)


def launch_program(command: str, args: tuple[str, ...] = ()) -> tuple[bool, str]:
    resolved = shutil.which(command)
    if not resolved:
        return False, f"{command} is not installed or not on PATH."
    subprocess.Popen([resolved, *args])
    suffix = f" to {args[0]}" if args else ""
    return True, f"Opened {command}{suffix}."


def _extract_url(text: str) -> str | None:
    match = URL_RE.search(text)
    return match.group(1) if match else None


def _normalize_url(url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"
