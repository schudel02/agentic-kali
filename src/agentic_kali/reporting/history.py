from __future__ import annotations

import json
from pathlib import Path


HISTORY_PATH = Path("reports/history.jsonl")


def append_history(report: dict, path: Path = HISTORY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "engagement": report.get("engagement"),
        "targets": report.get("targets", []),
        "findings": len(report.get("findings", [])),
        "report_files": report.get("report_files", {}),
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(summary) + "\n")


def read_history(path: Path = HISTORY_PATH) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

