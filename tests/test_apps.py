from agentic_kali.desktop.apps import parse_launch_request


def test_parse_launch_alias():
    request = parse_launch_request("open social engineering toolkit")
    assert request
    assert request.command == "setoolkit"
    assert request.risk == "approval_required"
    assert request.privileged


def test_parse_launch_normal_program():
    request = parse_launch_request("launch firefox")
    assert request
    assert request.command == "firefox"
    assert request.risk == "normal"
    assert not request.privileged
    assert not request.requires_tools_open


def test_parse_firefox_url():
    request = parse_launch_request("open firefox and go to example.com")
    assert request
    assert request.command == "firefox"
    assert request.args == ("https://example.com",)


def test_parse_run_tool_with_args_in_terminal():
    request = parse_launch_request("run nmap -sV 127.0.0.1 in terminal")
    assert request
    assert request.command == "nmap"
    assert request.args == ("-sV", "127.0.0.1")
    assert request.terminal
    assert request.requires_tools_open


def test_start_with_recon_is_not_tool_launch():
    assert parse_launch_request("lets start with recon") is None


def test_followup_run_phrases_are_not_tool_launches():
    assert parse_launch_request("run the next test") is None
    assert parse_launch_request("run it") is None


def test_clean_exec_strips_desktop_fields():
    from agentic_kali.desktop.apps import _clean_exec

    assert _clean_exec("firefox %u") == ["firefox"]


def test_terminal_tools_skip_desktop_launch(monkeypatch):
    import agentic_kali.desktop.apps as apps

    monkeypatch.setattr(apps, "_find_desktop_command", lambda _command: ["bad-desktop-launcher"])
    monkeypatch.setattr(apps, "_auth_prefix", lambda: [])
    monkeypatch.setattr(apps.shutil, "which", lambda command: f"/usr/bin/{command}")
    launched = []
    monkeypatch.setattr(apps.subprocess, "Popen", launched.append)

    ok, message = apps.launch_program("setoolkit", terminal=True)

    assert ok
    assert launched == [["/usr/bin/qterminal", "-e", "/usr/bin/setoolkit"]]
    assert "terminal" in message
