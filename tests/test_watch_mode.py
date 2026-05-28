from agentic_kali.desktop.watch import WatchMode
from agentic_kali.policy.models import Scope


def test_watch_mode_dry_plan():
    scope = Scope(engagement_name="x", targets=["127.0.0.1"], signed_permission=True)
    plan = WatchMode(scope).dry_plan("scan 127.0.0.1")
    assert "open terminal" in plan

