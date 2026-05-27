import os

from agentic_kali.ai.provider import AIProvider


def test_provider_uses_azure_when_configured(monkeypatch):
    called = {}

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")

    def fake_azure(prompt):
        called["prompt"] = prompt
        return ["ping_check"]

    monkeypatch.setattr(AIProvider, "_azure_responses", lambda self, prompt: fake_azure(prompt))
    assert AIProvider().suggest_actions("x") == ["ping_check"]
    assert called["prompt"] == "x"

