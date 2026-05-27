from __future__ import annotations

import re


def parse_nmap(stdout: str) -> dict:
    ports = []
    for line in stdout.splitlines():
        match = re.match(r"^(\d+)/(tcp|udp)\s+(\S+)\s+(\S+)(?:\s+(.+))?$", line.strip())
        if match:
            ports.append(
                {
                    "port": int(match.group(1)),
                    "protocol": match.group(2),
                    "state": match.group(3),
                    "service": match.group(4).strip(),
                    "version": (match.group(5) or "").strip(),
                }
            )
    return {"open_ports": ports}


def parse_whatweb(stdout: str) -> dict:
    technologies = []
    for token in re.findall(r"\[(.*?)\]", stdout):
        name = token.split(",", 1)[0].strip()
        if name:
            technologies.append(name)
    return {"technologies": sorted(set(technologies))}


def parse_httpx(stdout: str) -> dict:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    return {"responses": lines}
