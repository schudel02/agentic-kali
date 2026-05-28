from agentic_kali.desktop import lab


def test_parse_lab_request():
    request = lab.parse_lab_request("create a local test server")
    assert request
    assert request.kind == "basic-web"


def test_parse_lab_request_port():
    request = lab.parse_lab_request("start local lab server on port 8123")
    assert request
    assert request.port == 8123


def test_write_basic_web_lab(tmp_path):
    lab._write_basic_web_lab(tmp_path)
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "robots.txt").read_text(encoding="utf-8")
