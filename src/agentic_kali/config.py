from __future__ import annotations

import json
from pathlib import Path


CONFIG_PATH = Path("/etc/agentic-kali/config.json")


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        # Corrupt config — back it up and start fresh so the app can still launch
        import shutil
        backup = path.with_suffix(".json.bak")
        try:
            shutil.copy2(path, backup)
            path.unlink()
        except OSError:
            pass
        print(
            f"[agentic-kali] WARNING: Config file {path} is corrupt ({exc}).\n"
            f"  Backed up to {backup} and cleared. Re-run the config wizard to restore settings."
        )
        return {}


def get_setting(name: str, default: str = "") -> str:
    import os

    return os.getenv(name) or load_config().get(name, default)

