from __future__ import annotations

import hashlib
import json
from pathlib import Path


ADMIN_PATH = Path("/etc/agentic-kali/admin.json")
DEFAULT_PHRASE = "enable authorized admin mode"


def phrase_hash(phrase: str) -> str:
    return hashlib.sha256(phrase.encode("utf-8")).hexdigest()


def ensure_admin_config(path: Path = ADMIN_PATH) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"admin_phrase_sha256": phrase_hash(DEFAULT_PHRASE)}, indent=2), encoding="utf-8")


def is_admin_phrase(phrase: str, path: Path = ADMIN_PATH) -> bool:
    if not path.exists():
        return phrase.strip() == DEFAULT_PHRASE
    data = json.loads(path.read_text(encoding="utf-8"))
    expected = data.get("admin_phrase_sha256", "")
    return phrase_hash(phrase.strip()) == expected

