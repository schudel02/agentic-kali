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


def test_natural_preview_explains_sqlmap_action():
    prompt = object.__new__(FloatingPrompt)
    text = prompt._natural_event_text({"event": "action.started", "data": {"action": "sqlmap_safe", "target": "example.com"}})
    assert "Opening sqlmap" in text
    assert "without dumping data" in text


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
    assert tag == "transcript_result"
    assert text.startswith("RESULT")
    assert "Test run completed" in text


def test_preview_transcript_actions_are_italic_tag():
    prompt = object.__new__(FloatingPrompt)
    prompt.preview_mode = _Mode("transcript")
    _text, tag = prompt._preview_event_text({"time": "now", "event": "action.started", "data": {"action": "nmap_top_ports", "target": "example.com"}})
    assert tag == "transcript_action"


def test_preview_transcript_hides_noisy_internal_events():
    prompt = object.__new__(FloatingPrompt)
    prompt.preview_mode = _Mode("transcript")
    segments = prompt._preview_event_segments({"time": "now", "event": "ai.plan.proposed", "data": {"actions": []}})
    assert segments == []


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


def test_beginner_intro_guides_user():
    prompt = object.__new__(FloatingPrompt)
    prompt.user_mode = "Beginner"
    prompt.preferred_name = "Alex"
    text = prompt._mode_intro()
    assert "Hi Alex" in text
    assert "Whitehat Ethical Penetration Testing Agent" in text
    assert "simulated testing environment" in text


def test_target_explanation_has_examples():
    prompt = object.__new__(FloatingPrompt)
    text = prompt._target_explanation()
    assert "IP address" in text
    assert "Host/domain" in text
    assert "authorization" in text


def test_authorization_explanation_defines_permission():
    prompt = object.__new__(FloatingPrompt)
    text = prompt._authorization_explanation("example.com")
    assert "Authorization means" in text
    assert "type `authorized`" in text
    assert "choose another target" in text


def test_beginner_scope_prompts_are_stepwise():
    prompt = object.__new__(FloatingPrompt)
    prompt.beginner_scope = {"target": "example.com", "goal": "quick recon", "restrictions": "none"}
    assert "testing goal" in prompt._scope_goal_prompt()
    assert "restrictions" in prompt._scope_restrictions_prompt()
    assert "Scope is ready" in prompt._scope_ready_message()


def test_beginner_authorization_is_separate_step():
    prompt = object.__new__(FloatingPrompt)
    prompt.beginner_scope = {"target": "example.com"}
    text = prompt._authorization_explanation("example.com")
    assert "Authorization means" in text
    assert "type `authorized`" in text
