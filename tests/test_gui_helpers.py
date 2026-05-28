from agentic_kali.gui.floating import FloatingPrompt


class _Mode:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value


def test_finding_detail_explains_open_ports_plainly():
    prompt = object.__new__(FloatingPrompt)
    detail = prompt._finding_detail({"open_ports": [{"port": 80, "state": "open", "service": "http"}]})
    assert "Open network doors" in detail
    assert "80 (http)" in detail


def test_natural_preview_explains_nmap_action():
    prompt = object.__new__(FloatingPrompt)
    text = prompt._natural_event_text({"event": "action.started", "data": {"action": "nmap_top_ports", "target": "example.com"}})
    assert "Opening nmap" in text
    assert "doors into a system" in text


def test_preview_raw_mode_keeps_event_json():
    prompt = object.__new__(FloatingPrompt)
    prompt.preview_mode = _Mode("raw")
    text, tag = prompt._preview_event_text({"time": "now", "event": "run.completed", "data": {"findings": 2}})
    assert tag == "raw"
    assert "[now] run.completed" in text
    assert '"findings": 2' in text


def test_preview_transcript_mode_quotes_text():
    prompt = object.__new__(FloatingPrompt)
    prompt.preview_mode = _Mode("transcript")
    text, tag = prompt._preview_event_text({"time": "now", "event": "run.completed", "data": {"findings": 2}})
    assert tag == "transcript"
    assert text.startswith('"')
    assert "Test run completed" in text


def test_summary_explains_findings_in_laymens_terms():
    prompt = object.__new__(FloatingPrompt)
    report = {
        "findings": [
            {
                "title": "Nmap top ports scan",
                "target": "example.com",
                "severity": "info",
                "metadata": {"open_ports": [{"port": 443, "state": "open", "service": "https"}]},
            }
        ]
    }
    text = prompt._summarize_results(report, {"markdown": "reports/example.md"})
    assert "In plain English" in text
    assert "Why it matters" in text
    assert "What to do next" in text
    assert "open port as a door" in text
