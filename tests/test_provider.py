from agentic_kali.ai.provider import _parse_action_names


def test_parse_action_names():
    assert _parse_action_names('{"actions":["ping_check","nmap_top_ports"]}') == [
        "ping_check",
        "nmap_top_ports",
    ]


def test_parse_action_names_rejects_invalid_json():
    assert _parse_action_names("hello") == []

