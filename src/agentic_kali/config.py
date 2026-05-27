from __future__ import annotations

import json
from pathlib import Path


CONFIG_PATH = Path("/etc/agentic-kali/config.json")


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_setting(name: str, default: str = "") -> str:
    import os

    return os.getenv(name) or load_config().get(name, default)

