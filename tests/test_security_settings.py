from agentic_kali.policy.security_settings import ALL_ACTIONS, HIGH_RISK_TOOLS, UNSAFE_BUILD_TERMS, all_blocked_build_terms, load_admin_guardrails


def test_security_settings_are_centralized():
    assert "sqlmap_safe" in ALL_ACTIONS
    assert "sqlmap" in HIGH_RISK_TOOLS
    assert "phishing" in UNSAFE_BUILD_TERMS


def test_admin_guardrails_extend_blocked_terms(tmp_path):
    path = tmp_path / "guardrails.json"
    path.write_text('{"blocked_build_terms": ["custom-bad"]}', encoding="utf-8")
    assert load_admin_guardrails(path) == ("custom-bad",)
    assert "custom-bad" in all_blocked_build_terms(path)
