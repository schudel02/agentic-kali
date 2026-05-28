from agentic_kali.ai.commands import actions_from_command


def test_actions_from_command_matches_keywords():
    assert actions_from_command("scan ports", ["ping_check", "nmap_top_ports"]) == ["nmap_top_ports"]


def test_actions_from_command_falls_back_to_allowed_safe_actions():
    assert actions_from_command("do recon", ["ping_check"]) == ["ping_check"]


def test_domain_mapping_selects_web_mapping_actions():
    assert actions_from_command("proceed with domain mapping", ["whatweb", "httpx_probe"]) == ["whatweb", "httpx_probe"]


def test_sql_injection_selects_sqlmap_safe():
    assert actions_from_command("sql injection testing", ["sqlmap_safe", "nmap_top_ports"]) == ["sqlmap_safe"]


def test_vulnerability_selects_nuclei():
    assert actions_from_command("run vulnerability test", ["nuclei_safe", "nmap_top_ports"]) == ["nuclei_safe"]

