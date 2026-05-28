from __future__ import annotations

from typing import Callable

from agentic_kali.evidence.store import EvidenceStore
from agentic_kali.policy.models import Action
from agentic_kali.reporting.severity import rank_metadata
from agentic_kali.tools.parsers import parse_httpx, parse_nmap, parse_whatweb
from agentic_kali.tools.runner import run_command


class ToolRegistry:
    def __init__(self, evidence: EvidenceStore, should_stop: Callable[[], bool] | None = None) -> None:
        self.evidence = evidence
        self.should_stop = should_stop or (lambda: False)

    def run(self, action: Action) -> None:
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
