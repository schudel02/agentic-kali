from agentic_kali.desktop.apps import parse_launch_request


def test_parse_launch_alias():
    request = parse_launch_request("open social engineering toolkit")
    assert request
    assert request.command == "setoolkit"
    assert request.risk == "approval_required"


def test_parse_launch_normal_program():
    request = parse_launch_request("launch firefox")
    assert request
    assert request.command == "firefox"
    assert request.risk == "normal"


def test_parse_firefox_url():
    request = parse_launch_request("open firefox and go to example.com")
    assert request
    assert request.command == "firefox"
    assert request.args == ("https://example.com",)
