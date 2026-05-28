from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from urllib.parse import quote_plus


URL_RE = re.compile(r"\b((?:https?://)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?)\b")


@dataclass(frozen=True)
class BrowserRequest:
    action: str
    value: str = ""
    approval_required: bool = True


def parse_browser_request(text: str) -> BrowserRequest | None:
    lowered = text.lower().strip()
    if "browser" not in lowered and "firefox" not in lowered and "website" not in lowered:
        return None

    if "go back" in lowered or "back button" in lowered:
        return BrowserRequest("back")
    if "go forward" in lowered or "forward button" in lowered:
        return BrowserRequest("forward")
    if "refresh" in lowered or "reload" in lowered:
        return BrowserRequest("refresh")
    if "press enter" in lowered:
        return BrowserRequest("enter")

    type_match = re.search(r"\btype\s+(.+)$", text, re.IGNORECASE)
    if type_match:
        return BrowserRequest("type", type_match.group(1).strip())

    search_match = re.search(r"\bsearch(?: the web)? for\s+(.+)$", text, re.IGNORECASE)
    if search_match:
        query = quote_plus(search_match.group(1).strip())
        return BrowserRequest("open", f"https://www.google.com/search?q={query}")

    url_match = URL_RE.search(text)
    if url_match:
        return BrowserRequest("open", _normalize_url(url_match.group(1)))

    return None


def run_browser_request(request: BrowserRequest) -> tuple[bool, str]:
    if request.action == "open":
        return _run(["firefox", request.value], f"Opened Firefox to {request.value}.")
    if request.action == "back":
        return _run(["xdotool", "key", "Alt+Left"], "Sent browser Back.")
    if request.action == "forward":
        return _run(["xdotool", "key", "Alt+Right"], "Sent browser Forward.")
    if request.action == "refresh":
        return _run(["xdotool", "key", "ctrl+r"], "Refreshed browser.")
    if request.action == "enter":
        return _run(["xdotool", "key", "Return"], "Pressed Enter.")
    if request.action == "type":
        return _run(["xdotool", "type", "--delay", "15", request.value], "Typed into active browser field.")
    return False, f"Unsupported browser action: {request.action}"


def _run(command: list[str], success: str) -> tuple[bool, str]:
    if not shutil.which(command[0]):
        return False, f"{command[0]} is not installed or not on PATH."
    subprocess.Popen(command)
    return True, success


def _normalize_url(url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"

