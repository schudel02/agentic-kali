from __future__ import annotations

from agentic_kali.core.planner import ALL_ACTIONS


KEYWORDS = {
    "ping_check": ("ping", "check", "alive"),
    "nmap_top_ports": ("nmap", "port", "ports", "service"),
    "whatweb": ("whatweb", "fingerprint", "web", "mapping", "map", "domain"),
    "httpx_probe": ("httpx", "title", "tech", "http", "mapping", "map", "domain"),
    "nuclei_safe": ("nuclei", "template", "exposure", "misconfig"),
    "sqlmap_safe": ("sql injection", "sqli", "sqlmap"),
}


def actions_from_command(command: str, allowed_actions: list[str]) -> list[str]:
    text = command.lower()
    selected = [
        action
        for action, keywords in KEYWORDS.items()
        if action in allowed_actions and any(keyword in text for keyword in keywords)
    ]
    if selected:
        return selected
    return [action for action in ALL_ACTIONS if action in allowed_actions]

