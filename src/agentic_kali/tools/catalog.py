from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KaliTool:
    name: str
    category: str
    risk: str
    summary: str
    example: str


TOOLS = {
    "nmap": KaliTool(
        "nmap",
        "recon",
        "safe_auto",
        "Scans hosts and ports to identify exposed services and versions.",
        "nmap -Pn --top-ports 100 -sV 127.0.0.1",
    ),
    "whatweb": KaliTool(
        "whatweb",
        "web",
        "safe_auto",
        "Fingerprints web technologies like servers, frameworks, CMS, and headers.",
        "whatweb --no-errors http://127.0.0.1",
    ),
    "httpx": KaliTool(
        "httpx",
        "web",
        "safe_auto",
        "Probes HTTP services and reports titles, status codes, redirects, and technologies.",
        "httpx -silent -title -tech-detect -u http://127.0.0.1",
    ),
    "nuclei": KaliTool(
        "nuclei",
        "vulnerability scanning",
        "safe_auto_limited",
        "Runs template-based checks for exposures, misconfigurations, and known issues.",
        "nuclei -u http://127.0.0.1 -severity info,low -tags tech,exposure,misconfig",
    ),
    "gobuster": KaliTool(
        "gobuster",
        "content discovery",
        "approval_required",
        "Discovers hidden web paths, DNS names, or virtual hosts using wordlists.",
        "gobuster dir -u http://127.0.0.1 -w /usr/share/wordlists/dirb/common.txt",
    ),
    "ffuf": KaliTool(
        "ffuf",
        "fuzzing",
        "approval_required",
        "Fuzzes web paths, parameters, headers, vhosts, and request data.",
        "ffuf -u http://127.0.0.1/FUZZ -w /usr/share/wordlists/dirb/common.txt",
    ),
    "nikto": KaliTool(
        "nikto",
        "web scanning",
        "approval_required",
        "Checks web servers for risky files, outdated software, and common misconfigurations.",
        "nikto -h http://127.0.0.1",
    ),
    "sqlmap": KaliTool(
        "sqlmap",
        "database testing",
        "approval_required",
        "Tests authorized web parameters for SQL injection and database exposure.",
        "sqlmap -u 'http://127.0.0.1/page?id=1' --batch --risk=1 --level=1",
    ),
    "metasploit": KaliTool(
        "metasploit",
        "exploit validation",
        "lab_or_manual",
        "Framework for validating vulnerabilities in controlled, authorized environments.",
        "msfconsole",
    ),
    "hydra": KaliTool(
        "hydra",
        "credential testing",
        "credential_approval",
        "Tests password strength against authorized services using approved wordlists.",
        "hydra -l user -P approved-list.txt ssh://127.0.0.1",
    ),
}


def explain_tool(name: str) -> str | None:
    tool = TOOLS.get(name.lower())
    if not tool:
        return None
    return (
        f"{tool.name}: {tool.summary}\n"
        f"Category: {tool.category}\n"
        f"Risk: {tool.risk}\n"
        f"Example: {tool.example}"
    )


def recommend_tools(task: str) -> list[KaliTool]:
    text = task.lower()
    if any(word in text for word in ("web", "website", "http", "url")):
        return [TOOLS["whatweb"], TOOLS["httpx"], TOOLS["nuclei"], TOOLS["gobuster"]]
    if any(word in text for word in ("password", "credential", "login")):
        return [TOOLS["hydra"], TOOLS["nmap"]]
    if any(word in text for word in ("exploit", "vulnerability", "cve")):
        return [TOOLS["nmap"], TOOLS["nuclei"], TOOLS["nikto"], TOOLS["metasploit"]]
    return [TOOLS["nmap"], TOOLS["whatweb"], TOOLS["httpx"], TOOLS["nuclei"]]

