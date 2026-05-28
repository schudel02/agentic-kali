from agentic_kali.desktop.builder import build_custom_tool, is_safe_build_request, parse_build_request


def test_parse_build_request():
    request = parse_build_request("build a custom testing program for headers")
    assert request
    assert request.name


def test_blocks_unsafe_build_request():
    request = parse_build_request("build a custom tool for credential stealing")
    assert request
    assert not is_safe_build_request(request)


def test_build_custom_tool(tmp_path):
    request = parse_build_request("build a custom testing program for http headers")
    tool = build_custom_tool(request, output_dir=tmp_path)
    assert tool.path.exists()
    assert (tool.path / f"{tool.name}.py").exists()
    assert "python3" in tool.command
