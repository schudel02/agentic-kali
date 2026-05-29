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


def test_markdown_report_contains_scope():
    markdown = to_markdown(
        {
            "engagement": "x",
            "targets": ["127.0.0.1"],
            "scope": {
                "testing_goal": "quick recon",
                "restrictions": "none",
                "allowed_actions": ["ping_check"],
                "intrusive_allowed": False,
                "public_targets_allowed": False,
            },
            "findings": [],
        }
    )
    assert "## Scope" in markdown
    assert "quick recon" in markdown
    assert "Restrictions: none" in markdown

