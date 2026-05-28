from agentic_kali.ai.request import extract_target, summarize_request


def test_extract_domain_target():
    assert extract_target("test www.example.com") == "www.example.com"


def test_extract_localhost_target():
    assert extract_target("scan localhost") == "127.0.0.1"


def test_summarize_request():
    assert "127.0.0.1" in summarize_request("scan", ["nmap_top_ports"], "127.0.0.1")
