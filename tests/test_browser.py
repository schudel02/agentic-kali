from agentic_kali.desktop.browser import parse_browser_request


def test_parse_browser_open_url():
    request = parse_browser_request("open firefox and go to example.com")
    assert request
    assert request.action == "open"
    assert request.value == "https://example.com"


def test_parse_browser_search():
    request = parse_browser_request("browser search for kali linux")
    assert request
    assert request.action == "open"
    assert "kali+linux" in request.value


def test_parse_browser_refresh():
    request = parse_browser_request("refresh browser")
    assert request
    assert request.action == "refresh"

