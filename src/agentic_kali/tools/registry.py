from __future__ import annotations

from typing import Callable

from agentic_kali.evidence.store import EvidenceStore
from agentic_kali.policy.models import Action
from agentic_kali.reporting.severity import rank_metadata
from agentic_kali.tools.parsers import parse_httpx, parse_nmap, parse_whatweb
from agentic_kali.tools.runner import run_command

TOOL_DESCRIPTIONS = {
    "ping_check": "Validating the target is inside the approved workflow.",
    "nmap_top_ports": "Opening nmap and checking common exposed services.",
    "whatweb": "Opening WhatWeb and fingerprinting web technology.",
    "httpx_probe": "Opening httpx and probing HTTP titles, status codes, and technologies.",
    "nuclei_safe": "Opening nuclei and running low-risk exposure checks.",
    "nuclei_full": "Opening nuclei with medium/high severity templates (admin mode).",
    "sqlmap_safe": "Opening sqlmap in conservative mode to check for SQL injection indicators.",
    "gobuster_dir": "Opening gobuster for directory and file discovery.",
    "ffuf_fuzz": "Opening ffuf for web path fuzzing.",
    "nikto_scan": "Opening nikto for web server vulnerability scanning.",
    "hydra_brute": "Opening hydra for authorized credential testing.",
}


class ToolRegistry:
    def __init__(self, evidence: EvidenceStore, should_stop: Callable[[], bool] | None = None) -> None:
        self.evidence = evidence
        self.should_stop = should_stop or (lambda: False)

    def run(self, action: Action) -> None:
        self.evidence.log("tool.description", {"action": action.name, "target": action.target, "description": TOOL_DESCRIPTIONS.get(action.name, "Running selected tool.")})
        if action.name == "ping_check":
            self._ping_check(action)
            return
        if action.name == "nmap_top_ports":
            self._nmap_top_ports(action)
            return
        if action.name == "whatweb":
            self._whatweb(action)
            return
        if action.name == "httpx_probe":
            self._httpx_probe(action)
            return
        if action.name == "nuclei_safe":
            self._nuclei_safe(action)
            return
        if action.name == "sqlmap_safe":
            self._sqlmap_safe(action)
            return
        if action.name == "gobuster_dir":
            self._gobuster_dir(action)
            return
        if action.name == "ffuf_fuzz":
            self._ffuf_fuzz(action)
            return
        if action.name == "nikto_scan":
            self._nikto_scan(action)
            return
        if action.name == "hydra_brute":
            self._hydra_brute(action)
            return
        if action.name == "nuclei_full":
            self._nuclei_full(action)
            return

        self.evidence.log("tool.skipped", {"action": action.name, "reason": "unknown tool"})

    def _ping_check(self, action: Action) -> None:
        self.evidence.finding(
            title="Recon placeholder completed",
            target=action.target,
            severity="info",
            evidence=f"Validated policy-controlled execution for {action.target}.",
        )

    def _nmap_top_ports(self, action: Action) -> None:
        result = run_command(["nmap", "-Pn", "--top-ports", "100", "-sV", action.target], timeout=180, should_stop=self.should_stop)
        self.evidence.log("tool.nmap_top_ports", result.as_dict())
        self._record_result("Nmap top ports scan", action, result.as_dict(), parse_nmap)

    def _whatweb(self, action: Action) -> None:
        result = run_command(["whatweb", "--no-errors", action.target], timeout=120, should_stop=self.should_stop)
        self.evidence.log("tool.whatweb", result.as_dict())
        self._record_result("Web fingerprint", action, result.as_dict(), parse_whatweb)

    def _httpx_probe(self, action: Action) -> None:
        result = run_command(["httpx", "-silent", "-title", "-tech-detect", "-u", action.target], timeout=120, should_stop=self.should_stop)
        self.evidence.log("tool.httpx_probe", result.as_dict())
        self._record_result("HTTP probe", action, result.as_dict(), parse_httpx)

    def _nuclei_safe(self, action: Action) -> None:
        result = run_command(
            [
                "nuclei",
                "-u",
                action.target,
                "-severity",
                "info,low",
                "-tags",
                "tech,exposure,misconfig",
                "-jsonl",
            ],
            timeout=240,
            should_stop=self.should_stop,
        )
        self.evidence.log("tool.nuclei_safe", result.as_dict())
        self._record_result("Nuclei safe templates", action, result.as_dict())

    def _sqlmap_safe(self, action: Action) -> None:
        result = run_command(
            ["sqlmap", "-u", action.target, "--batch", "--risk=1", "--level=1", "--smart"],
            timeout=240,
            should_stop=self.should_stop,
        )
        self.evidence.log("tool.sqlmap_safe", result.as_dict())
        self._record_result("SQL injection safe check", action, result.as_dict())

    def _gobuster_dir(self, action: Action) -> None:
        wordlist = "/usr/share/wordlists/dirb/common.txt"
        result = run_command(
            ["gobuster", "dir", "-u", action.target, "-w", wordlist, "-q"],
            timeout=300,
            should_stop=self.should_stop,
        )
        self.evidence.log("tool.gobuster_dir", result.as_dict())
        self._record_result("Gobuster directory discovery", action, result.as_dict())

    def _ffuf_fuzz(self, action: Action) -> None:
        wordlist = "/usr/share/wordlists/dirb/common.txt"
        url = action.target.rstrip("/") + "/FUZZ"
        result = run_command(
            ["ffuf", "-u", url, "-w", wordlist, "-mc", "200,204,301,302,403", "-s"],
            timeout=300,
            should_stop=self.should_stop,
        )
        self.evidence.log("tool.ffuf_fuzz", result.as_dict())
        self._record_result("ffuf web fuzzing", action, result.as_dict())

    def _nikto_scan(self, action: Action) -> None:
        result = run_command(
            ["nikto", "-h", action.target, "-nointeractive"],
            timeout=360,
            should_stop=self.should_stop,
        )
        self.evidence.log("tool.nikto_scan", result.as_dict())
        self._record_result("Nikto web scan", action, result.as_dict())

    def _hydra_brute(self, action: Action) -> None:
        result = run_command(
            ["hydra", "-L", "/usr/share/wordlists/metasploit/unix_users.txt",
             "-P", "/usr/share/wordlists/metasploit/unix_passwords.txt",
             "-t", "4", f"ssh://{action.target}"],
            timeout=300,
            should_stop=self.should_stop,
        )
        self.evidence.log("tool.hydra_brute", result.as_dict())
        self._record_result("Hydra credential test", action, result.as_dict())

    def _nuclei_full(self, action: Action) -> None:
        result = run_command(
            ["nuclei", "-u", action.target, "-severity", "info,low,medium,high", "-jsonl"],
            timeout=360,
            should_stop=self.should_stop,
        )
        self.evidence.log("tool.nuclei_full", result.as_dict())
        self._record_result("Nuclei full scan", action, result.as_dict())

    def _record_result(self, title: str, action: Action, result: dict, parser=None) -> None:
        metadata = {}
        if not result["found"]:
            severity = "info"
            evidence = result["stderr"]
        elif result["returncode"] == 0:
            severity = "info"
            evidence = result["stdout"] or "Tool completed without output."
            if parser:
                metadata = parser(result["stdout"])
                severity = rank_metadata(metadata)
        else:
            severity = "low"
            evidence = result["stderr"] or result["stdout"]

        self.evidence.finding(
            title=title,
            target=action.target,
            severity=severity,
            evidence=evidence,
            metadata=metadata,
        )
