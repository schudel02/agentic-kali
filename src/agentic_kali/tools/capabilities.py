from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    key: str
    title: str
    purpose: str
    actions: tuple[str, ...]
    risk: str


CAPABILITIES = (
    Capability(
        "quick_recon",
        "Quick Recon",
        "Find live services and basic web technologies.",
        ("ping_check", "nmap_top_ports", "whatweb", "httpx_probe"),
        "safe_auto",
    ),
    Capability(
        "web_fingerprint",
        "Web Fingerprint",
        "Identify web server, frameworks, titles, redirects, and exposed metadata.",
        ("whatweb", "httpx_probe"),
        "safe_auto",
    ),
    Capability(
        "safe_vuln_check",
        "Safe Vulnerability Check",
        "Run limited low-risk checks for exposures and misconfigurations.",
        ("nuclei_safe",),
        "safe_auto_limited",
    ),
    Capability(
        "content_discovery",
        "Content Discovery",
        "Look for hidden web paths or vhosts. Can be noisy.",
        ("gobuster", "ffuf"),
        "approval_required",
    ),
    Capability(
        "web_server_review",
        "Web Server Review",
        "Check common web server issues, risky files, and misconfigurations.",
        ("nikto",),
        "approval_required",
    ),
    Capability(
        "credential_audit",
        "Credential Audit",
        "Test approved password policy or login controls with explicit authorization.",
        ("hydra",),
        "credential_approval",
    ),
    Capability(
        "exploit_validation",
        "Exploit Validation",
        "Validate likely vulnerabilities in a lab or with manual approval.",
        ("metasploit",),
        "lab_or_manual",
    ),
)


def capability_menu() -> str:
    lines = ["Here are the pentest workflows I can help with:"]
    for item in CAPABILITIES:
        actions = ", ".join(item.actions)
        lines.append(f"- {item.title} [{item.key}] - {item.purpose} Tools/actions: {actions}. Risk: {item.risk}.")
    return "\n".join(lines)


def find_capability(text: str) -> Capability | None:
    lowered = text.lower()
    for item in CAPABILITIES:
        if item.key in lowered or item.title.lower() in lowered:
            return item
    return None

