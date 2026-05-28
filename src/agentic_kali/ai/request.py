from __future__ import annotations

import re


TARGET_RE = re.compile(
    r"\b((?:https?://)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}|(?:\d{1,3}\.){3}\d{1,3}|localhost)\b"
)


def extract_target(command: str) -> str | None:
    match = TARGET_RE.search(command)
    if not match:
        return None
    target = match.group(1)
    if target.startswith(("http://", "https://")):
        return target
    if target == "localhost":
        return "127.0.0.1"
    return target


def summarize_request(command: str, actions: list[str], target: str | None) -> str:
    target_text = target or "the configured scope"
    action_text = ", ".join(actions) if actions else "safe recon"
    return f"I'll test {target_text} with {action_text}, then summarize findings and recommendations."


def wants_tool_run(command: str) -> bool:
    text = command.lower()
    run_words = ("run", "scan", "test", "pentest", "check", "enumerate", "probe", "fingerprint")
    target = extract_target(command)
    return target is not None and any(word in text for word in run_words)


def is_capability_question(command: str) -> bool:
    text = command.lower()
    phrases = (
        "what can you do",
        "what can you all do",
        "what testing can you do",
        "show tests",
        "list tests",
        "capabilities",
    )
    return any(phrase in text for phrase in phrases)
