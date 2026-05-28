from agentic_kali.ai.request import is_capability_question, wants_tool_run, wants_tool_run_intent


def test_capability_question_variants():
    assert is_capability_question("what can you all do?")
    assert is_capability_question("what all can you do?")
    assert is_capability_question("show tests")


def test_wants_tool_run_requires_target():
    assert wants_tool_run("scan 127.0.0.1")
    assert not wants_tool_run("what can you do?")


def test_wants_tool_run_intent_without_target():
    assert wants_tool_run_intent("run vulnerability test")
    assert wants_tool_run_intent("scan it")
