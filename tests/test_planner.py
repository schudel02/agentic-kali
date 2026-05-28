from agentic_kali.ai.planner import AIPlanner
from agentic_kali.evidence.store import EvidenceStore
from agentic_kali.policy.models import Scope


def test_planner_only_uses_allowed_safe_actions():
    scope = Scope(
        engagement_name="x",
        targets=["127.0.0.1"],
        allowed_actions=["ping_check", "not_real"],
        signed_permission=True,
    )
    actions = AIPlanner(scope, EvidenceStore()).propose_next_actions()
    assert [action.name for action in actions] == ["ping_check"]


def test_planner_uses_command_keywords():
    scope = Scope(
        engagement_name="x",
        targets=["127.0.0.1"],
        allowed_actions=["ping_check", "nmap_top_ports"],
        signed_permission=True,
    )
    actions = AIPlanner(scope, EvidenceStore(), command="scan ports").propose_next_actions()
    assert [action.name for action in actions] == ["nmap_top_ports"]


def test_planner_marks_sqlmap_safe_intrusive():
    scope = Scope(
        engagement_name="x",
        targets=["127.0.0.1"],
        allowed_actions=["sqlmap_safe"],
        signed_permission=True,
        intrusive_allowed=True,
    )
    actions = AIPlanner(scope, EvidenceStore(), command="sql injection testing").propose_next_actions()
    assert [action.name for action in actions] == ["sqlmap_safe"]
    assert actions[0].intrusive


def test_planner_prompt_allows_scoped_intrusive_actions():
    scope = Scope(
        engagement_name="x",
        targets=["127.0.0.1"],
        allowed_actions=["sqlmap_safe"],
        signed_permission=True,
        intrusive_allowed=True,
    )
    prompt = AIPlanner(scope, EvidenceStore(), command="sql injection testing")._prompt()
    assert "sqlmap_safe" in prompt
    assert "Intrusive allowed: True" in prompt
