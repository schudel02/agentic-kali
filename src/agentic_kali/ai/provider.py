from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

from agentic_kali.config import get_setting


class APIKeyError(Exception):
    """Raised when an API key is invalid, expired, or missing permissions."""
    def __init__(self, provider: str, code: int, detail: str) -> None:
        self.provider = provider
        self.code = code
        self.detail = detail
        super().__init__(f"{provider} API key error ({code}): {detail}")


_ERROR_HINTS: dict[int, str] = {
    401: "Invalid or expired API key. Check the key is copied correctly with no extra spaces.",
    403: "This key does not have permission for this model or endpoint.",
    429: "Rate limit reached or quota exceeded. Check your plan/credits.",
    500: "Provider server error — try again in a moment.",
}


def _hint(code: int, body: str) -> str:
    base = _ERROR_HINTS.get(code, f"HTTP {code} error.")
    if "credit" in body.lower() or "balance" in body.lower():
        base += " Your account may be out of credits."
    if "invalid_api_key" in body.lower() or "authentication" in body.lower():
        base = "Invalid API key. Go to console.anthropic.com and verify your key."
    return base


def validate_anthropic_key(api_key: str) -> str:
    """Test an Anthropic key with a minimal request. Returns 'ok' or an error message."""
    body = json.dumps({
        "model": "claude-haiku-4-5",
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "ping"}],
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
        with urllib.request.urlopen(req, timeout=10):
            return "ok"
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        return _hint(exc.code, body_text)
    except Exception as exc:
        return f"Connection error: {exc}"


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
        model = get_setting("ANTHROPIC_MODEL", "claude-haiku-4-5")

        # Separate system from turns
        system_text = ""
        turns: list[dict] = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                turns.append({"role": msg["role"], "content": msg["content"]})

        if not turns:
            turns = [{"role": "user", "content": "Hello"}]

        # Cache the system prompt — static across the whole session
        system_block = [
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }
        ] if system_text else system_text

        # Cache conversation history: mark the last assistant turn as a cache breakpoint
        # so we only pay full price for the new user message on each call
        cached_turns = []
        for i, turn in enumerate(turns):
            if i == len(turns) - 2 and turn["role"] == "assistant":
                # Last assistant message — mark as cache breakpoint
                cached_turns.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": turn["content"],
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                })
            else:
                cached_turns.append(turn)

        body = json.dumps({
            "model": model,
            "max_tokens": 1024,
            "system": system_block,
            "messages": cached_turns,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "prompt-caching-2024-07-31",
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
            hint = _hint(exc.code, body_text)
            raise APIKeyError("Anthropic", exc.code, hint) from exc
        except APIKeyError:
            raise
        except Exception as exc:
            return f"[Claude connection error: {exc}]"

    def _claude_actions(self, prompt: str) -> list[str]:
        """Action planning call with prompt caching.

        The large static block (tool catalog + instructions) is cached.
        Only the small dynamic block (current command, findings, history) is sent fresh.
        """
        from agentic_kali.policy.security_settings import ALL_ADMIN_ACTIONS

        api_key = get_setting("ANTHROPIC_API_KEY")
        model = get_setting("ANTHROPIC_MODEL", "claude-haiku-4-5")

        # Static cacheable system: planner role + full tool catalog
        # This block is identical on every call — gets cached after the first request
        static_system = (
            "You are a penetration testing action planner for Agent Kal. "
            "Return ONLY valid JSON in the format {\"actions\":[\"action_name\"]}. "
            "No explanation, no markdown, just the JSON object.\n\n"
            f"Full tool catalog ({len(ALL_ADMIN_ACTIONS)} actions available):\n"
            + "\n".join(f"- {a}" for a in ALL_ADMIN_ACTIONS)
        )

        # Split the prompt: extract the dynamic part (everything after "Known actions:")
        # so the static tool list in the system block isn't duplicated in the user message
        dynamic_prompt = prompt
        if "Known actions:" in prompt:
            # Keep only scope + command + history + findings — drop the redundant tool list
            parts = prompt.split("Scope allowed actions:")
            if len(parts) == 2:
                dynamic_prompt = "Scope allowed actions:" + parts[1]

        body = json.dumps({
            "model": model,
            "max_tokens": 256,
            "system": [
                {
                    "type": "text",
                    "text": static_system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [{"role": "user", "content": dynamic_prompt}],
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "prompt-caching-2024-07-31",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = _claude_extract_text(data)
            return _parse_action_names(text)
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise APIKeyError("Anthropic", exc.code, _hint(exc.code, body_text)) from exc
        except APIKeyError:
            raise
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
