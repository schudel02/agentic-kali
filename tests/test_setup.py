import builtins

from agentic_kali.setup import run_config_wizard


def test_config_wizard_writes_file(monkeypatch, tmp_path):
    answers = iter(["endpoint", "key", "deployment", "2025-04-01-preview"])
    monkeypatch.setattr(builtins, "input", lambda _: next(answers))
    path = tmp_path / "config.json"
    config = run_config_wizard(path)
    assert config["AZURE_OPENAI_ENDPOINT"] == "endpoint"
    assert path.exists()

