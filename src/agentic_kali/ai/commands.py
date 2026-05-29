from __future__ import annotations

from agentic_kali.policy.security_settings import ALL_ACTIONS


KEYWORDS = {
    "ping_check": ("ping", "check", "alive"),
    "nmap_top_ports": ("nmap", "port", "ports", "service"),
    "whatweb": ("whatweb", "fingerprint", "web", "mapping", "map", "domain"),
    "httpx_probe": ("httpx", "title", "tech", "http", "mapping", "map", "domain"),
    "nuclei_safe": ("nuclei", "template", "exposure", "misconfig", "vulnerability", "vulnerabilities", "vuln"),
    "sqlmap_safe": ("sql injection", "sqli", "sqlmap"),
}


def actions_from_command(
    command: str,
    allowed_actions: list[str],
    already_done: list[str] | None = None,
) -> list[str]:
    text = command.lower()
    done = set(already_done or [])
    selected = [
        action
        for action, keywords in KEYWORDS.items()
        if action in allowed_actions and any(keyword in text for keyword in keywords)
    ]
    if selected:
        return selected
    # No keyword match — return allowed actions not yet completed
    remaining = [a for a in ALL_ACTIONS if a in allowed_actions and a not in done]
    return remaining or [action for action in ALL_ACTIONS if action in allowed_actions]

