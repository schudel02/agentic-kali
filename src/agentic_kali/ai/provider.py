from __future__ import annotations

import json
import os
import urllib.request

from agentic_kali.config import get_setting


class AIProvider:
    def chat(self, messages: list[dict[str, str]]) -> str:
        if get_setting("AZURE_OPENAI_API_KEY") and get_setting("AZURE_OPENAI_ENDPOINT"):
            return self._azure_chat(messages)
        return ""

    def suggest_actions(self, prompt: str) -> list[str]:
        if get_setting("AZURE_OPENAI_API_KEY") and get_setting("AZURE_OPENAI_ENDPOINT"):
            return self._azure_responses(prompt)
        if os.getenv("OPENAI_API_KEY"):
            return self._openai_responses(prompt)
        return []

    def _openai_responses(self, prompt: str) -> list[str]:
        if not os.getenv("OPENAI_API_KEY"):
            return []

        body = json.dumps(
            {
                "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                "input": prompt,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=body,
            headers={
                "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        text = _extract_text(data)
        return _parse_action_names(text)

    def _azure_chat(self, messages: list[dict[str, str]]) -> str:
        endpoint = get_setting("AZURE_OPENAI_ENDPOINT").rstrip("/")
        api_version = get_setting("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
        deployment = get_setting("AZURE_OPENAI_DEPLOYMENT", get_setting("OPENAI_MODEL", "gpt-4.1-mini"))
        url = f"{endpoint}/openai/responses?api-version={api_version}"

        prompt = "\n".join(f"{message['role']}: {message['content']}" for message in messages)
        body = json.dumps({"model": deployment, "input": prompt}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "api-key": get_setting("AZURE_OPENAI_API_KEY"),
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            return ""

        return _extract_text(data).strip()

    def _azure_responses(self, prompt: str) -> list[str]:
        endpoint = get_setting("AZURE_OPENAI_ENDPOINT").rstrip("/")
        api_version = get_setting("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
        deployment = get_setting("AZURE_OPENAI_DEPLOYMENT", get_setting("OPENAI_MODEL", "gpt-4.1-mini"))
        url = f"{endpoint}/openai/responses?api-version={api_version}"

        body = json.dumps({"model": deployment, "input": prompt}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "api-key": get_setting("AZURE_OPENAI_API_KEY"),
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        text = _extract_text(data)
        return _parse_action_names(text)


def _extract_text(data: dict) -> str:
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "\n".join(chunks)


def _parse_action_names(text: str) -> list[str]:
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
