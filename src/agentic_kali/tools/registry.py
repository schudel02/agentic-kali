from __future__ import annotations

import re
import shlex
import subprocess
import threading
from typing import Callable

_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


# Tools that cannot handle http:// URLs — need bare host or host:port
_HOST_ONLY_TOOLS = {
    "ping_check", "nmap_top_ports", "nmap_full", "nmap_udp", "nmap_vuln",
    "netdiscover", "arp_scan", "dmitry", "dnsrecon", "dnsenum",
    "amass_passive", "subfinder", "sublist3r", "assetfinder",
    "theharvester", "enum4linux", "crackmapexec", "netexec",
    "hydra_brute", "medusa", "smtp_user_enum",
    "impacket_secretsdump", "impacket_psexec", "impacket_getuserspns",
}


def _normalize_target(action_name: str, target: str) -> str:
    """Strip http(s):// from targets for tools that need bare host/port."""
    if action_name not in _HOST_ONLY_TOOLS:
        return target
    # Remove scheme
    cleaned = re.sub(r"^https?://", "", target)
    # Remove trailing slash and path
    cleaned = cleaned.split("/")[0]
    return cleaned

_BURP_PROCESS: subprocess.Popen | None = None
_BURP_LOCK = threading.Lock()

from agentic_kali.evidence.store import EvidenceStore
from agentic_kali.policy.models import Action
from agentic_kali.reporting.severity import rank_metadata
from agentic_kali.tools.catalog import TOOLS
from agentic_kali.tools.parsers import parse_httpx, parse_nmap, parse_whatweb
from agentic_kali.tools.runner import run_command

# Parsers for structured output extraction
_PARSERS: dict[str, object] = {
    "nmap_top_ports": parse_nmap,
    "nmap_full": parse_nmap,
    "nmap_udp": parse_nmap,
    "nmap_vuln": parse_nmap,
    "whatweb": parse_whatweb,
    "httpx_probe": parse_httpx,
}

# Timeouts per action (seconds)
_TIMEOUTS: dict[str, int] = {
    "nmap_top_ports": 180,
    "nmap_full": 600,
    "nmap_udp": 300,
    "nmap_vuln": 300,
    "nuclei_safe": 300,
    "nuclei_full": 480,
    "gobuster_dir": 360,
    "gobuster_dns": 360,
    "ffuf_fuzz": 300,
    "feroxbuster": 300,
    "dirsearch": 300,
    "nikto_scan": 420,
    "wpscan": 300,
    "hydra_brute": 300,
    "medusa": 300,
    "autorecon": 600,
    "aircrack_ng": 120,
    "wifite": 120,
}
_DEFAULT_TIMEOUT = 120


class ToolRegistry:
    def __init__(self, evidence: EvidenceStore, should_stop: Callable[[], bool] | None = None) -> None:
        self.evidence = evidence
        self.should_stop = should_stop or (lambda: False)

    def run(self, action: Action) -> None:
        # Special: launch Burp Suite GUI as background process
        if action.name == "burpsuite":
            self._launch_burpsuite(action)
            return

        tool = TOOLS.get(action.name)
        if not tool:
            self.evidence.log("tool.skipped", {"action": action.name, "reason": "unknown tool"})
            return

        self.evidence.log("tool.description", {
            "action": action.name,
            "target": action.target,
            "description": tool.summary,
        })

        # Proxy-dependent tools: ensure Burp is running first
        if action.name in {"burp_proxy_scan", "burp_spider"}:
            self._ensure_burp_running()

        # Normalize target for tools that can't handle URLs
        effective_target = _normalize_target(action.name, action.target)

        # Build command list
        args_str = tool.args_template.replace("{target}", effective_target)
        if args_str.strip():
            cmd = [tool.command] + shlex.split(args_str)
        else:
            cmd = [tool.command]

        timeout = _TIMEOUTS.get(action.name, _DEFAULT_TIMEOUT)
        result = run_command(cmd, timeout=timeout, should_stop=self.should_stop)

        event_key = f"tool.{action.name}"
        self.evidence.log(event_key, result.as_dict())

        parser = _PARSERS.get(action.name)
        self._record_result(tool.summary, action, result.as_dict(), parser)

    def _launch_burpsuite(self, action: Action) -> None:
        global _BURP_PROCESS
        import shutil
        import time
        if not shutil.which("burpsuite"):
            self.evidence.finding(
                title="Burp Suite not installed",
                target=action.target,
                severity="info",
                evidence="burpsuite command not found. Install with: sudo apt install burpsuite",
            )
            return
        with _BURP_LOCK:
            if _BURP_PROCESS and _BURP_PROCESS.poll() is None:
                self.evidence.finding(
                    title="Burp Suite already running",
                    target=action.target,
                    severity="info",
                    evidence="Burp Suite is already running. Proxy listening on 127.0.0.1:8080.",
                )
                return
            try:
                _BURP_PROCESS = subprocess.Popen(
                    ["burpsuite"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(4)  # Give Burp time to start proxy
                self.evidence.finding(
                    title="Burp Suite launched",
                    target=action.target,
                    severity="info",
                    evidence=(
                        "Burp Suite opened. Proxy listening on 127.0.0.1:8080.\n"
                        "Subsequent proxy-aware tools will route traffic through Burp.\n"
                        "Use the Burp UI to review intercepted requests, run active scanner, "
                        "and configure scope."
                    ),
                )
            except Exception as exc:
                self.evidence.finding(
                    title="Burp Suite launch failed",
                    target=action.target,
                    severity="info",
                    evidence=str(exc),
                )

    def _ensure_burp_running(self) -> None:
        global _BURP_PROCESS
        import shutil, time
        with _BURP_LOCK:
            if _BURP_PROCESS and _BURP_PROCESS.poll() is None:
                return
            if shutil.which("burpsuite"):
                _BURP_PROCESS = subprocess.Popen(
                    ["burpsuite"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(4)

    def _record_result(self, title: str, action: Action, result: dict, parser=None) -> None:
        metadata: dict = {}
        if not result["found"]:
            severity = "info"
            evidence = result["stderr"] or f"{result['command'][0] if result['command'] else 'tool'} not installed on this system"
        elif result["returncode"] == 0:
            severity = "info"
            raw = _strip_ansi(result["stdout"] or "")
            evidence = raw or "Tool completed without output."
            if parser:
                metadata = parser(raw)
                severity = rank_metadata(metadata)
        else:
            raw_err = _strip_ansi(result["stderr"] or "")
            raw_out = _strip_ansi(result["stdout"] or "")
            severity = "low"
            evidence = raw_err or raw_out or "Tool exited with non-zero code."

        self.evidence.finding(
            title=title,
            target=action.target,
            severity=severity,
            evidence=evidence,
            metadata=metadata,
        )
