from agentic_kali.ai.commands import actions_from_command


def test_actions_from_command_matches_keywords():
    assert actions_from_command("scan ports", ["ping_check", "nmap_top_ports"]) == ["nmap_top_ports"]


def test_actions_from_command_falls_back_to_allowed_safe_actions():
    assert actions_from_command("do recon", ["ping_check"]) == ["ping_check"]

