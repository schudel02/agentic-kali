from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

from agentic_kali.config import get_setting


class AIProvider:
    """Multi-provider AI backend.

    Priority order:
      1. Anthropic Claude  (ANTHROPIC_API_KEY)
      2. Azure OpenAI      (AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT)
      3. OpenAI            (OPENAI_API_KEY)
      4. None              (returns empty / fallback)
    """

    def chat(self, messages: list[dict[str, str]]) -> str:
        if get_setting("ANTHROPIC_API_KEY"):
            return self._claude_chat(messages)
        if get_setting("AZURE_OPENAI_API_KEY") and get_setting("AZURE_OPENAI_ENDPOINT"):
            return self._azure_chat(messages)
        if os.getenv("OPENAI_API_KEY"):
            return self._openai_chat(messages)
        return ""

    def suggest_actions(self, prompt: str) -> list[str]:
        if get_setting("ANTHROPIC_API_KEY"):
            return self._claude_actions(prompt)
        if get_setting("AZURE_OPENAI_API_KEY") and get_setting("AZURE_OPENAI_ENDPOINT"):
            return self._azure_responses(prompt)
        if os.getenv("OPENAI_API_KEY"):
            return self._openai_responses(prompt)
        return []

    # ── Anthropic Claude ───────────────────────────────────────────────

    def _claude_chat(self, messages: list[dict[str, str]]) -> str:
        api_key = get_setting("ANTHROPIC_API_KEY")
        model = get_setting("ANTHROPIC_MODEL", "claude-sonnet-4-5")

        # Separate system message from user/assistant turns
        system = ""
        turns: list[dict] = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                turns.append({"role": msg["role"], "content": msg["content"]})

        if not turns:
            turns = [{"role": "user", "content": "Hello"}]

        body = json.dumps({
            "model": model,
            "max_tokens": 1024,
            "system": system,
            "messages": turns,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return _claude_extract_text(data)
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            return f"[Claude API error {exc.code}: {body_text[:200]}]"
        except Exception as exc:
            return f"[Claude error: {exc}]"

    def _claude_actions(self, prompt: str) -> list[str]:
        api_key = get_setting("ANTHROPIC_API_KEY")
        model = get_setting("ANTHROPIC_MODEL", "claude-haiku-4-5")

        body = json.dumps({
            "model": model,
            "max_tokens": 256,
            "system": (
                "You are a penetration testing action planner. "
                "Return ONLY valid JSON in the format {\"actions\":[\"action_name\"]}. "
                "No explanation, no markdown, just the JSON object."
            ),
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = _claude_extract_text(data)
            return _parse_action_names(text)
        except Exception:
            return []

    # ── OpenAI ─────────────────────────────────────────────────────────

    def _openai_chat(self, messages: list[dict[str, str]]) -> str:
        api_key = os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        body = json.dumps({"model": model, "messages": messages}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception:
            return ""

    def _openai_responses(self, prompt: str) -> list[str]:
        api_key = os.getenv("OPENAI_API_KEY", "")
        body = json.dumps({
            "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            "input": prompt,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return _parse_action_names(_extract_openai_text(data))
        except Exception:
            return []

    # ── Azure OpenAI ───────────────────────────────────────────────────

    def _azure_chat(self, messages: list[dict[str, str]]) -> str:
        endpoint = get_setting("AZURE_OPENAI_ENDPOINT").rstrip("/")
        api_version = get_setting("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
        deployment = get_setting("AZURE_OPENAI_DEPLOYMENT", get_setting("OPENAI_MODEL", "gpt-4.1-mini"))
        url = f"{endpoint}/openai/responses?api-version={api_version}"
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        body = json.dumps({"model": deployment, "input": prompt}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={"api-key": get_setting("AZURE_OPENAI_API_KEY"), "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return _extract_openai_text(data).strip()
        except Exception:
            return ""

    def _azure_responses(self, prompt: str) -> list[str]:
        endpoint = get_setting("AZURE_OPENAI_ENDPOINT").rstrip("/")
        api_version = get_setting("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
        deployment = get_setting("AZURE_OPENAI_DEPLOYMENT", get_setting("OPENAI_MODEL", "gpt-4.1-mini"))
        url = f"{endpoint}/openai/responses?api-version={api_version}"
        body = json.dumps({"model": deployment, "input": prompt}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={"api-key": get_setting("AZURE_OPENAI_API_KEY"), "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return _parse_action_names(_extract_openai_text(data))
        except Exception:
            return []


# ── Helpers ────────────────────────────────────────────────────────────

def _claude_extract_text(data: dict) -> str:
    for block in data.get("content", []):
        if block.get("type") == "text":
            return block.get("text", "")
    return ""


def _extract_openai_text(data: dict) -> str:
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "\n".join(chunks)


def _parse_action_names(text: str) -> list[str]:
    # Try to find JSON even if surrounded by other text
    import re
    match = re.search(r'\{[^{}]*"actions"\s*:\s*\[.*?\]\s*\}', text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    actions = data.get("actions", [])
    if not isinstance(actions, list):
        return []
    return [item for item in actions if isinstance(item, str)]
