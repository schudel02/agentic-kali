from agentic_kali.ai.request import is_capability_question, wants_tool_run


def test_capability_question_variants():
    assert is_capability_question("what can you all do?")
    assert is_capability_question("show tests")


def test_wants_tool_run_requires_target():
    assert wants_tool_run("scan 127.0.0.1")
    assert not wants_tool_run("what can you do?")

