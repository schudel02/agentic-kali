from __future__ import annotations

import json
from pathlib import Path

from agentic_kali.config import CONFIG_PATH


def run_config_wizard(path: Path = CONFIG_PATH) -> dict:
    print("Agentic Kali config wizard")
    print("\nProvider priority: Claude > Azure OpenAI > OpenAI\n")

    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass

    config = {
        # Anthropic Claude (highest priority)
        "ANTHROPIC_API_KEY": _ask("Anthropic API key (Claude)", existing.get("ANTHROPIC_API_KEY", "")),
        "ANTHROPIC_MODEL": _ask("Claude model", existing.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")),
        # Azure OpenAI
        "AZURE_OPENAI_ENDPOINT": _ask("Azure OpenAI endpoint", existing.get("AZURE_OPENAI_ENDPOINT", "")),
        "AZURE_OPENAI_API_KEY": _ask("Azure OpenAI API key", existing.get("AZURE_OPENAI_API_KEY", "")),
        "AZURE_OPENAI_DEPLOYMENT": _ask("Azure OpenAI deployment", existing.get("AZURE_OPENAI_DEPLOYMENT", "")),
        "AZURE_OPENAI_API_VERSION": _ask("Azure OpenAI API version", existing.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")),
    }
    # Strip blank entries so they don't shadow env vars
    config = {k: v for k, v in config.items() if v}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"\nSaved to {path}")
    return config


def _ask(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default

