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
