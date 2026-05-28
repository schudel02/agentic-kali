from __future__ import annotations

import re


TARGET_RE = re.compile(
    r"\b((?:https?://)?(?:[a-zA-Z0-9-]+[\.,])+(?:[a-zA-Z]{2,})|(?:\d{1,3}\.){3}\d{1,3}|localhost)\b"
)


def extract_target(command: str) -> str | None:
    match = TARGET_RE.search(command)
    if not match:
        return None
    target = match.group(1)
    target = _normalize_domain_typo(target)
    if target.startswith(("http://", "https://")):
        return target
    if target == "localhost":
        return "127.0.0.1"
    return target


def _normalize_domain_typo(target: str) -> str:
    if re.search(r"[a-zA-Z0-9-],[a-zA-Z]{2,}(?:/|$)", target):
        return target.replace(",", ".")
    return target


def summarize_request(command: str, actions: list[str], target: str | None) -> str:
    target_text = target or "the configured scope"
    action_text = ", ".join(actions) if actions else "safe recon"
    if "recon" in command.lower():
        return f"I'll perform reconnaissance on {target_text}: mapping reachable services, web technologies, and response details so we can choose later vulnerability tests."
    return f"I'll test {target_text} with {action_text}, then summarize findings and recommendations."


def wants_tool_run(command: str) -> bool:
    text = command.lower()
    run_words = ("run", "scan", "test", "pentest", "check", "enumerate", "probe", "fingerprint")
    target = extract_target(command)
    return target is not None and any(word in text for word in run_words)


def wants_tool_run_intent(command: str) -> bool:
    text = command.lower()
    run_phrases = (
        "run vulnerability test",
        "run vulnerability scan",
        "vulnerability test",
        "vulnerability scan",
        "start with recon",
        "start recon",
        "quick recon",
        "run tests",
        "run test",
        "domain mapping",
        "map domain",
        "mapping",
        "proceed with domain mapping",
        "scan it",
        "test it",
        "check it",
        "scan that",
        "test that",
    )
    run_words = ("scan", "test", "pentest", "check", "enumerate", "probe", "fingerprint", "recon", "mapping")
    return any(phrase in text for phrase in run_phrases) or any(word in text for word in run_words)


def is_capability_question(command: str) -> bool:
    text = command.lower()
    phrases = (
        "what can you do",
        "what can you all do",
        "what all can you do",
        "what testing can you do",
        "show tests",
        "list tests",
        "capabilities",
    )
    return any(phrase in text for phrase in phrases)
