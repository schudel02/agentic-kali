from agentic_kali.policy.security_settings import ALL_ACTIONS, HIGH_RISK_TOOLS, UNSAFE_BUILD_TERMS


def test_security_settings_are_centralized():
    assert "sqlmap_safe" in ALL_ACTIONS
    assert "sqlmap" in HIGH_RISK_TOOLS
    assert "phishing" in UNSAFE_BUILD_TERMS

