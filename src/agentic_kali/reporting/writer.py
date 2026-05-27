from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def write_reports(report: dict, output_dir: Path = Path("reports")) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    base = output_dir / f"{report['engagement']}-{stamp}"

    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")

    return {"json": str(json_path), "markdown": str(md_path)}


def to_markdown(report: dict) -> str:
    lines = [
        f"# {report['engagement']}",
        "",
        "## Targets",
        "",
        *[f"- {target}" for target in report["targets"]],
        "",
        "## Findings",
        "",
    ]

    if not report["findings"]:
        lines.append("No findings.")
    else:
        for finding in report["findings"]:
            lines.extend(
                [
                    f"### {finding['title']}",
                    "",
                    f"- Target: `{finding['target']}`",
                    f"- Severity: `{finding['severity']}`",
                    "",
                    "```text",
                    finding["evidence"].strip(),
                    "```",
                    "",
                ]
            )
            if finding.get("metadata"):
                lines.extend(["Metadata:", "", "```json", json.dumps(finding["metadata"], indent=2), "```", ""])

    return "\n".join(lines)
