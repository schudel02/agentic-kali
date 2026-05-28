from agentic_kali.ai.chat import ChatSession


def test_chat_fallback():
    session = ChatSession()
    response = session.reply("help me scan 127.0.0.1")
    assert "scope" in response.lower() or "ready" in response.lower()

