import builtins

from agentic_kali.setup import run_config_wizard


def test_config_wizard_writes_file(monkeypatch, tmp_path):
    # Wizard now asks: claude key, claude model, azure endpoint, azure key, azure deployment, azure version
    answers = iter(["sk-ant-test", "claude-sonnet-4-5", "endpoint", "azkey", "deployment", "2025-04-01-preview"])
    monkeypatch.setattr(builtins, "input", lambda _: next(answers))
    path = tmp_path / "config.json"
    config = run_config_wizard(path)
    assert config.get("ANTHROPIC_API_KEY") == "sk-ant-test"
    assert config.get("AZURE_OPENAI_ENDPOINT") == "endpoint"
    assert path.exists()

