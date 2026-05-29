from __future__ import annotations

from agentic_kali.policy.security_settings import ALL_ACTIONS, ALL_ADMIN_ACTIONS


KEYWORDS = {
    "ping_check": ("ping", "check alive", "is up", "reachable"),
    "nmap_top_ports": ("nmap", "port scan", "ports", "service scan", "service detect"),
    "whatweb": ("whatweb", "fingerprint", "web fingerprint", "web tech"),
    "httpx_probe": ("httpx", "http probe", "http title", "tech detect"),
    "nuclei_safe": ("nuclei", "template", "exposure", "misconfig", "vulnerability", "vuln check"),
    "nuclei_full": ("nuclei full", "full nuclei", "medium", "high severity"),
    "sqlmap_safe": ("sql injection", "sqli", "sqlmap"),
    "gobuster_dir": ("gobuster", "directory", "dir scan", "dirb", "path discovery"),
    "ffuf_fuzz": ("ffuf", "fuzz", "fuzzing"),
    "nikto_scan": ("nikto", "web server scan", "web scan"),
    "hydra_brute": ("hydra", "brute force", "credential test", "password test"),
    "api_probe": ("api probe", "api check", "api headers", "rest api", "graphql", "swagger", "openapi"),
    "api_discover": ("api discover", "api endpoints", "api parameters", "api enum", "find endpoints"),
    "api_fuzz": ("api fuzz", "fuzz api", "api wordlist"),
    "api_nuclei": ("api scan", "api vuln", "api vulnerability"),
    "burpsuite": ("burp suite", "burpsuite", "open burp", "launch burp", "start burp"),
    "burp_proxy_scan": ("burp scan", "scan through burp", "proxy scan", "burp proxy"),
}

AUTO_PHRASES = ("you choose", "auto", "autonomous", "automatically", "decide for me", "pick for me", "you pick")
ALL_PHRASES = ("run all", "all tests", "everything", "all tools", "full scan", "full test")


def actions_from_command(
    command: str,
    allowed_actions: list[str],
    already_done: list[str] | None = None,
) -> list[str]:
    text = command.lower()
    done = set(already_done or [])
    all_known = list(ALL_ADMIN_ACTIONS)

    # "run all" → everything allowed not yet done
    if any(phrase in text for phrase in ALL_PHRASES):
        return [a for a in all_known if a in allowed_actions and a not in done] or list(allowed_actions)

    # Explicit tool name mentioned
    selected = [
        action
        for action, keywords in KEYWORDS.items()
        if action in allowed_actions and any(keyword in text for keyword in keywords)
    ]
    if selected:
        return selected

    # Numbered selection (e.g. "1", "2 and 3", "1,3")
    import re
    numbers = [int(n) for n in re.findall(r"\b([1-9])\b", text)]
    if numbers:
        menu = [a for a in all_known if a in allowed_actions]
        picked = [menu[n - 1] for n in numbers if 1 <= n <= len(menu)]
        if picked:
            return picked

    # "quick recon" shortcut
    if "quick recon" in text or "recon" in text:
        recon = ["ping_check", "nmap_top_ports", "whatweb", "httpx_probe"]
        return [a for a in recon if a in allowed_actions]

    # No match — return remaining allowed actions not yet done
    remaining = [a for a in all_known if a in allowed_actions and a not in done]
    return remaining or [a for a in all_known if a in allowed_actions]


def is_auto_command(command: str) -> bool:
    text = command.lower()
    return any(phrase in text for phrase in AUTO_PHRASES)

