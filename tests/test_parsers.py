from agentic_kali.tools.parsers import parse_httpx, parse_nmap, parse_whatweb


def test_parse_nmap_open_ports():
    parsed = parse_nmap("22/tcp open ssh OpenSSH 9.6\n80/tcp closed http\n")
    assert parsed["open_ports"][0]["port"] == 22
    assert parsed["open_ports"][0]["service"] == "ssh"


def test_parse_whatweb_technologies():
    parsed = parse_whatweb("http://x [200 OK] [Apache] [PHP/8.2]")
    assert parsed["technologies"] == ["200 OK", "Apache", "PHP/8.2"]


def test_parse_httpx_responses():
    parsed = parse_httpx("https://x [200] [Title]\n")
    assert parsed["responses"] == ["https://x [200] [Title]"]
