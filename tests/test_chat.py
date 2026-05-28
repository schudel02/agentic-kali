from agentic_kali.ai.chat import ChatSession


def test_chat_fallback():
    session = ChatSession()
    response = session.reply("help me scan 127.0.0.1")
    assert "scope" in response.lower() or "ready" in response.lower()


def test_chat_explains_authorized_target():
    response = ChatSession().reply("what do you mean by authorized target?")
    assert "permission" in response.lower()


def test_chat_handles_bare_target():
    response = ChatSession().reply("127.0.0.1")
    assert "what would you like" in response.lower()


def test_chat_suggests_scope_after_common_tests():
    session = ChatSession()
    response = session.reply("what are the most common penetration tests used by professionals?")
    assert "would you like" in response.lower()

    followup = session.reply("yes")
    assert "recommended" in followup.lower()
    assert "what target" in followup.lower()


def test_chat_beginner_walkthrough():
    response = ChatSession().reply("I'm new to pen testing but I want to run some tests")
    lower = response.lower()
    assert "walk you through" in lower
    assert "what would you like to test" in lower
    assert "generate a report" in lower
