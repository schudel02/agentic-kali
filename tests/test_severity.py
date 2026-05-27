from agentic_kali.reporting.severity import rank_metadata


def test_high_risk_port():
    assert rank_metadata({"open_ports": [{"port": 445, "state": "open"}]}) == "high"


def test_medium_risk_port():
    assert rank_metadata({"open_ports": [{"port": 80, "state": "open"}]}) == "medium"


def test_closed_port_info():
    assert rank_metadata({"open_ports": [{"port": 80, "state": "closed"}]}) == "info"

