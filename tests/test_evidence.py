from agentic_kali.evidence.store import EvidenceStore


def test_event_callback_runs():
    seen = []
    store = EvidenceStore(on_event=seen.append)
    store.log("x", {"ok": True})
    assert seen[0]["event"] == "x"

