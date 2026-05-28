from __future__ import annotations

from agentic_kali.ai.provider import AIProvider
from agentic_kali.tools.capabilities import capability_menu, find_capability
from agentic_kali.tools.catalog import explain_tool, recommend_tools


SYSTEM_PROMPT = (
    "You are Agent Kal, a friendly Kali Linux pentest assistant. "
    "Be conversational, concise, and beginner-friendly. "
    "Only discuss authorized security testing. "
    "If a user asks to test a target, explain the safe plan and mention scope/permission. "
    "Do not provide stealth, persistence, credential theft, or destructive guidance."
)


class ChatSession:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def reply(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})
        response = AIProvider().chat(self.messages)
        if not response:
            response = self._fallback(user_message)
        self.messages.append({"role": "assistant", "content": response})
        return response

    @staticmethod
    def _fallback(user_message: str) -> str:
        lower = user_message.lower()
        if "what can you do" in lower or "testing can you do" in lower or "show tests" in lower:
            return capability_menu()
        capability = find_capability(lower)
        if capability:
            return (
                f"{capability.title}: {capability.purpose}\n"
                f"I would use: {', '.join(capability.actions)}.\n"
                f"Risk level: {capability.risk}.\n"
                "Tell me the authorized target and I can prepare the scoped run."
            )
        if lower.startswith("what is ") or lower.startswith("what does "):
            for token in lower.replace("?", "").split():
                explanation = explain_tool(token)
                if explanation:
                    return explanation
        if "recommend" in lower or "what tool" in lower:
            tools = recommend_tools(user_message)
            return "I recommend:\n" + "\n".join(f"- {tool.name}: {tool.summary} ({tool.risk})" for tool in tools)
        if "pentest" in user_message.lower() or "scan" in user_message.lower():
            return "I can help with that. First I’ll check the authorized scope, then run safe recon tools and explain each result."
        return "I’m ready. Tell me the authorized target and what you want to learn about it."
