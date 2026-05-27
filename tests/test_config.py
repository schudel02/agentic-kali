from agentic_kali.config import get_setting, load_config


def test_load_config_missing(tmp_path):
    assert load_config(tmp_path / "missing.json") == {}


def test_get_setting_prefers_env(monkeypatch, tmp_path):
    monkeypatch.setenv("X_TEST_SETTING", "env")
    assert get_setting("X_TEST_SETTING") == "env"

