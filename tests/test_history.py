from agentic_kali.reporting.history import append_history, read_history


def test_history_round_trip(tmp_path):
    path = tmp_path / "history.jsonl"
    append_history({"engagement": "x", "targets": ["127.0.0.1"], "findings": [{}]}, path)
    history = read_history(path)
    assert history[0]["engagement"] == "x"
    assert len(history[0]["findings"]) == 1

