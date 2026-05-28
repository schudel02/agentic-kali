from __future__ import annotations

from agentic_kali.ai.provider import AIProvider
from agentic_kali.ai.request import is_capability_question
from agentic_kali.desktop.apps import parse_launch_request
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
        launch = parse_launch_request(user_message)
        if launch:
            if launch.risk == "approval_required":
                return (
                    f"I can open {launch.display_name}. It is a high-risk pentest tool, so I’ll ask for approval first. "
                    "I can launch it, but I won’t automate phishing, credential theft, stealth, or unauthorized activity."
                )
            return f"I can open {launch.display_name} for you."
        if is_capability_question(user_message):
            return capability_menu()
        if "authorized target" in lower or "scope" in lower:
            return (
                "An authorized target is a system you have explicit permission to test. "
                "Examples: 127.0.0.1, your lab VM IP, or a client system listed in your agreement. "
                "I use scope to make sure I only run tests where you have permission."
            )
        if lower.strip().replace(".", "").isdigit() or lower.strip() == "localhost":
            return (
                f"I see target {user_message.strip()}. What would you like me to do with it? "
                "You can say: quick recon, safe vulnerability check, web fingerprint, or show tests."
            )
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
        return (
            "I can help with authorized pentesting. Ask 'what all can you do?' for a menu, "
            "or give me a scoped target and a goal like 'run quick recon on 127.0.0.1'."
        )
