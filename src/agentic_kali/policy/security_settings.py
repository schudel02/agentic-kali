from __future__ import annotations

import json
from pathlib import Path

ADMIN_GUARDRAILS = Path("/etc/agentic-kali/guardrails.json")

SAFE_RECON_ACTIONS = ("ping_check", "nmap_top_ports", "whatweb", "httpx_probe", "nuclei_safe")
INTRUSIVE_ACTIONS = ("sqlmap_safe",)
ALL_ACTIONS = (*SAFE_RECON_ACTIONS, *INTRUSIVE_ACTIONS)
ADMIN_EXTRA_ACTIONS = ("gobuster_dir", "ffuf_fuzz", "nikto_scan", "hydra_brute", "nuclei_full")
ALL_ADMIN_ACTIONS = (*ALL_ACTIONS, *ADMIN_EXTRA_ACTIONS)

HIGH_RISK_TOOLS = {"setoolkit", "msfconsole", "hydra", "sqlmap"}
PRIVILEGED_TOOLS = {"wireshark", "setoolkit"}
TERMINAL_TOOLS = {"setoolkit", "msfconsole"}

UNSAFE_BUILD_TERMS = (
    "credential",
    "password steal",
    "token steal",
    "phishing",
    "keylogger",
    "persistence",
    "backdoor",
    "ransomware",
    "exfiltrate",
    "destructive",
)


def load_admin_guardrails(path: Path = ADMIN_GUARDRAILS) -> tuple[str, ...]:
    if not path.exists():
        return ()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    terms = data.get("blocked_build_terms", [])
    if not isinstance(terms, list):
        return ()
    return tuple(str(term).strip().lower() for term in terms if str(term).strip())


def all_blocked_build_terms(path: Path = ADMIN_GUARDRAILS) -> tuple[str, ...]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if "all_blocked_terms" in data:
                terms = data["all_blocked_terms"]
                if isinstance(terms, list):
                    return tuple(str(t).strip().lower() for t in terms if str(t).strip())
        except (OSError, json.JSONDecodeError):
            pass
    return tuple(dict.fromkeys([*UNSAFE_BUILD_TERMS, *load_admin_guardrails(path)]))
