from __future__ import annotations

import shlex
from typing import Callable

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
        tool = TOOLS.get(action.name)
        if not tool:
            self.evidence.log("tool.skipped", {"action": action.name, "reason": "unknown tool"})
            return

        self.evidence.log("tool.description", {
            "action": action.name,
            "target": action.target,
            "description": tool.summary,
        })

        # Build command list
        args_str = tool.args_template.replace("{target}", action.target)
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

    def _record_result(self, title: str, action: Action, result: dict, parser=None) -> None:
        metadata: dict = {}
        if not result["found"]:
            severity = "info"
            evidence = result["stderr"] or f"{result['command'][0] if result['command'] else 'tool'} not installed on this system"
        elif result["returncode"] == 0:
            severity = "info"
            evidence = result["stdout"] or "Tool completed without output."
            if parser:
                metadata = parser(result["stdout"])
                severity = rank_metadata(metadata)
        else:
            severity = "low"
            evidence = result["stderr"] or result["stdout"] or "Tool exited with non-zero code."

        self.evidence.finding(
            title=title,
            target=action.target,
            severity=severity,
            evidence=evidence,
            metadata=metadata,
        )
