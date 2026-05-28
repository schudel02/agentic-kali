from agentic_kali.policy.security_settings import SAFE_RECON_ACTIONS


def test_nuclei_safe_is_allowlisted():
    assert "nuclei_safe" in SAFE_RECON_ACTIONS

