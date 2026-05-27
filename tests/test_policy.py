from agentic_kali.policy.gate import PolicyGate
from agentic_kali.policy.models import Action, Scope


def test_denies_without_permission():
    scope = Scope(engagement_name="x", targets=["127.0.0.1"])
    decision = PolicyGate(scope).evaluate(Action(name="ping_check", target="127.0.0.1"))
    assert not decision.allowed
    assert decision.reason == "explicit permission not confirmed"


def test_allows_scoped_safe_action():
    scope = Scope(
        engagement_name="x",
        targets=["127.0.0.1"],
        allowed_actions=["ping_check"],
        signed_permission=True,
    )
    decision = PolicyGate(scope).evaluate(Action(name="ping_check", target="127.0.0.1"))
    assert decision.allowed


def test_requires_manual_approval_mode():
    scope = Scope(
        engagement_name="x",
        targets=["127.0.0.1"],
        allowed_actions=["ping_check"],
        approval_mode="approval_required",
        signed_permission=True,
    )
    decision = PolicyGate(scope).evaluate(Action(name="ping_check", target="127.0.0.1"))
    assert decision.approval_required


def test_blocks_public_target_without_flag():
    scope = Scope(
        engagement_name="x",
        targets=["8.8.8.8"],
        allowed_actions=["ping_check"],
        signed_permission=True,
    )
    decision = PolicyGate(scope).evaluate(Action(name="ping_check", target="8.8.8.8"))
    assert not decision.allowed
    assert "public target" in decision.reason


def test_allows_public_target_with_flag():
    scope = Scope(
        engagement_name="x",
        targets=["8.8.8.8"],
        allowed_actions=["ping_check"],
        signed_permission=True,
        public_targets_allowed=True,
    )
    decision = PolicyGate(scope).evaluate(Action(name="ping_check", target="8.8.8.8"))
    assert decision.allowed
