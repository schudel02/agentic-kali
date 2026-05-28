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
    lines.append("Would you like to perform one of these tests?")
    return "\n".join(lines)


def recommended_scope() -> str:
    return (
        "Yes. Here is my recommended safe beginner scope:\n"
        "- Engagement name: authorized recon\n"
        "- Targets: tell me the IP, domain, or lab host you have permission to test\n"
        "- Actions: ping_check, nmap_top_ports, whatweb, httpx_probe, nuclei_safe\n"
        "- Approval mode: recon_only, or Admin Mode if you already enabled it\n"
        "- Permission: type AUTHORIZED in Settings\n\n"
        "What target do you want to test?"
    )


def beginner_walkthrough() -> str:
    return (
        "Okay. Since you're new to pentesting, I'll walk you through it step by step.\n\n"
        "What would you like to test?\n"
        "- Local machine or lab VM\n"
        "- Website or web app you own or have permission to test\n"
        "- Internal network host\n"
        "- A single service like SSH, HTTP, or SMB\n\n"
        "Beginner path I recommend:\n"
        "1. Confirm scope and permission.\n"
        "2. Run quick recon to find live services.\n"
        "3. Fingerprint web/software versions.\n"
        "4. Run safe vulnerability checks.\n"
        "5. Review findings and recommended fixes.\n"
        "6. Generate a report with evidence and next steps.\n\n"
        "Send the target you are authorized to test, like `I authorize testing of 127.0.0.1`, and I'll guide the run."
    )


def find_capability(text: str) -> Capability | None:
    lowered = text.lower()
    for item in CAPABILITIES:
        if item.key in lowered or item.title.lower() in lowered:
            return item
    return None
