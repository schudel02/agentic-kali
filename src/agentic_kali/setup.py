from __future__ import annotations

import json
from pathlib import Path

from agentic_kali.config import CONFIG_PATH


def run_config_wizard(path: Path = CONFIG_PATH) -> dict:
    print("Agentic Kali config wizard")
    config = {
        "AZURE_OPENAI_ENDPOINT": _ask("Azure OpenAI endpoint", ""),
        "AZURE_OPENAI_API_KEY": _ask("Azure OpenAI API key", ""),
        "AZURE_OPENAI_DEPLOYMENT": _ask("Azure OpenAI deployment", ""),
        "AZURE_OPENAI_API_VERSION": _ask("Azure OpenAI API version", "2025-04-01-preview"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def _ask(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default

