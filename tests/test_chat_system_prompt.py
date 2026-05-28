from agentic_kali.ai.chat import SYSTEM_PROMPT


def test_system_prompt_mentions_local_app_launching():
    assert "launch approved Kali programs" in SYSTEM_PROMPT
