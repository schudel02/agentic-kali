from __future__ import annotations


HIGH_RISK_PORTS = {21, 23, 445, 3389}
MEDIUM_RISK_PORTS = {22, 25, 53, 80, 110, 143, 443, 3306, 5432, 6379, 8080}


def rank_metadata(metadata: dict) -> str:
    ports = metadata.get("open_ports", [])
    open_ports = {item["port"] for item in ports if item.get("state") == "open"}

    if open_ports & HIGH_RISK_PORTS:
        return "high"
    if open_ports & MEDIUM_RISK_PORTS:
        return "medium"
    if ports or metadata.get("technologies") or metadata.get("responses"):
        return "info"
    return "info"

