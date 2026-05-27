from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable


class EvidenceStore:
    def __init__(self, on_event: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.events: list[dict[str, Any]] = []
        self.findings: list[dict[str, Any]] = []
        self.on_event = on_event

    def log(self, event: str, data: dict[str, Any]) -> None:
        record = {
            "time": datetime.now(UTC).isoformat(),
            "event": event,
            "data": data,
        }
        self.events.append(record)
        if self.on_event:
            self.on_event(record)

    def finding(
        self,
        title: str,
        target: str,
        severity: str,
        evidence: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.findings.append(
            {
                "title": title,
                "target": target,
                "severity": severity,
                "evidence": evidence,
                "metadata": metadata or {},
            }
        )
