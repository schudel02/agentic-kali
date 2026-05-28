from __future__ import annotations

import re
import shlex
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
TERMINAL_TOOLS = {"setoolkit", "msfconsole"}
KNOWN_TOOLS = set(ALIASES.values()) | {"qterminal", "x-terminal-emulator", "terminal"}


@dataclass(frozen=True)
class LaunchRequest:
    display_name: str
    command: str
    risk: str
    args: tuple[str, ...] = ()
    privileged: bool = False
    terminal: bool = False
    requires_tools_open: bool = False


def parse_launch_request(text: str) -> LaunchRequest | None:
    lowered = text.lower().strip()
    match = re.search(r"\b(?:open|launch|start|run|use)\s+(.+)$", text, re.IGNORECASE)
    if not match:
        if lowered in {"terminal", "open terminal", "start terminal", "start terminal session"}:
            return LaunchRequest(display_name="terminal", command="qterminal", risk="normal")
        return None

    requested = match.group(1).strip().strip(".?!")
    requested_lower = requested.lower()
    terminal = "terminal" in requested_lower or "shell" in requested_lower
    requested_clean = re.sub(r"\b(?:in|inside|with)\s+(?:a\s+)?(?:terminal|shell)\b", "", requested, flags=re.IGNORECASE).strip()
    parts = _split_command(requested_clean)
    if not parts:
        return LaunchRequest(display_name="terminal", command="qterminal", risk="normal")
    alias_key = requested_clean.lower()
    command = ALIASES.get(alias_key, ALIASES.get(parts[0].lower(), parts[0]))
    url = _extract_url(requested)
    if requested_lower.startswith("firefox") and url:
        command = "firefox"
    command = re.sub(r"[^a-zA-Z0-9._+-]", "", command)
    if not command:
        return None

    risk = "approval_required" if command in HIGH_RISK else "normal"
    if command in {"firefox", "xdg-open"} and url:
        args = (_normalize_url(url),)
    elif command == parts[0]:
        args = tuple(parts[1:])
    else:
        args = ()
    return LaunchRequest(
        display_name=requested,
        command=command,
        risk=risk,
        args=args,
        privileged=command in PRIVILEGED,
        terminal=terminal or command in TERMINAL_TOOLS,
        requires_tools_open=command not in KNOWN_TOOLS,
    )


def launch_program(command: str, args: tuple[str, ...] = (), privileged: bool = False, terminal: bool = False) -> tuple[bool, str]:
    auth = _auth_prefix() if privileged else []
    if privileged and not auth:
        return False, "This tool needs admin rights, but pkexec/sudo is not available."
    desktop = None if terminal or command in TERMINAL_TOOLS else _find_desktop_command(command)
    if desktop and not args:
        subprocess.Popen([*auth, *desktop])
        suffix = " Kali may ask for your password." if privileged else ""
        return True, f"Opened {command}.{suffix}"

    if command in {"qterminal", "x-terminal-emulator", "terminal"} and not args:
        terminal_path = _terminal()
        if not terminal_path:
            return False, "No terminal emulator found."
        subprocess.Popen([terminal_path])
        return True, "Opened a terminal session."

    resolved = shutil.which(command)
    if not resolved:
        return False, f"{command} is not installed or not on PATH."
    if terminal or command in TERMINAL_TOOLS:
        terminal_path = _terminal()
        if terminal_path:
            subprocess.Popen([*auth, terminal_path, "-e", resolved, *args])
            suffix = " Kali may ask for your password." if privileged else ""
            return True, f"Opened {command} in a terminal.{suffix}"
    subprocess.Popen([*auth, resolved, *args])
    suffix = f" to {args[0]}" if args else ""
    auth_note = " Kali may ask for your password." if privileged else ""
    return True, f"Opened {command}{suffix}.{auth_note}"


def _terminal() -> str | None:
    return shutil.which("qterminal") or shutil.which("x-terminal-emulator") or shutil.which("gnome-terminal")


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


def _split_command(value: str) -> list[str]:
    try:
        return shlex.split(value)
    except ValueError:
        return value.split()


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
