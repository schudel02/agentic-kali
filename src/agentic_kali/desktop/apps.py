from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

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
PRIVILEGED = {"wireshark", "setoolkit"}


@dataclass(frozen=True)
class LaunchRequest:
    display_name: str
    command: str
    risk: str
    args: tuple[str, ...] = ()
    privileged: bool = False


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
    return LaunchRequest(display_name=requested, command=command, risk=risk, args=args, privileged=command in PRIVILEGED)


def launch_program(command: str, args: tuple[str, ...] = (), privileged: bool = False) -> tuple[bool, str]:
    desktop = _find_desktop_command(command)
    auth = _auth_prefix() if privileged else []
    if privileged and not auth:
        return False, "This tool needs admin rights, but pkexec/sudo is not available."
    if desktop and not args:
        subprocess.Popen([*auth, *desktop])
        suffix = " Kali may ask for your password." if privileged else ""
        return True, f"Opened {command}.{suffix}"

    resolved = shutil.which(command)
    if not resolved:
        return False, f"{command} is not installed or not on PATH."
    if command in {"setoolkit", "msfconsole"}:
        terminal = shutil.which("qterminal") or shutil.which("x-terminal-emulator")
        if terminal:
            subprocess.Popen([*auth, terminal, "-e", resolved, *args])
            suffix = " Kali may ask for your password." if privileged else ""
            return True, f"Opened {command} in a terminal.{suffix}"
    subprocess.Popen([*auth, resolved, *args])
    suffix = f" to {args[0]}" if args else ""
    auth_note = " Kali may ask for your password." if privileged else ""
    return True, f"Opened {command}{suffix}.{auth_note}"


def _auth_prefix() -> list[str]:
    pkexec = shutil.which("pkexec")
    if pkexec:
        return [pkexec]
    sudo = shutil.which("sudo")
    if sudo:
        return [sudo]
    return []


def _extract_url(text: str) -> str | None:
    match = URL_RE.search(text)
    return match.group(1) if match else None


def _normalize_url(url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def _find_desktop_command(name: str) -> list[str] | None:
    search_dirs = [Path("/usr/share/applications"), Path.home() / ".local/share/applications"]
    terms = {name.lower(), name.lower().replace("-", " ")}
    for directory in search_dirs:
        if not directory.exists():
            continue
        for desktop_file in directory.glob("*.desktop"):
            try:
                data = desktop_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            app_name = _desktop_value(data, "Name").lower()
            exec_value = _desktop_value(data, "Exec")
            if not exec_value:
                continue
            if name.lower() in desktop_file.stem.lower() or any(term in app_name for term in terms):
                command = _clean_exec(exec_value)
                if command:
                    return command
    return None


def _desktop_value(data: str, key: str) -> str:
    prefix = f"{key}="
    for line in data.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def _clean_exec(value: str) -> list[str]:
    parts = [part for part in value.split() if not part.startswith("%")]
    return parts
