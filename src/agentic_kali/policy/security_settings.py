from __future__ import annotations

SAFE_RECON_ACTIONS = ("ping_check", "nmap_top_ports", "whatweb", "httpx_probe", "nuclei_safe")
INTRUSIVE_ACTIONS = ("sqlmap_safe",)
ALL_ACTIONS = (*SAFE_RECON_ACTIONS, *INTRUSIVE_ACTIONS)

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

