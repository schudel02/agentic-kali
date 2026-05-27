from agentic_kali.reporting.writer import to_markdown


def test_markdown_report_contains_findings():
    markdown = to_markdown(
        {
            "engagement": "x",
            "targets": ["127.0.0.1"],
            "findings": [
                {
                    "title": "Finding",
                    "target": "127.0.0.1",
                    "severity": "info",
                    "evidence": "ok",
                }
            ],
        }
    )
    assert "# x" in markdown
    assert "Finding" in markdown

