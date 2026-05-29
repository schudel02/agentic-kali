from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KaliTool:
    name: str
    category: str
    risk: str
    summary: str
    command: str
    args_template: str = "{target}"
    requires_admin: bool = False


# Full Kali tool catalog — action_name -> KaliTool
TOOLS: dict[str, KaliTool] = {
    # ── Recon / Discovery ──────────────────────────────────────────────
    "nmap_top_ports": KaliTool(
        "nmap", "recon", "safe_auto",
        "Port scan and service detection (top 100 ports).",
        "nmap", "-Pn --top-ports 100 -sV {target}",
    ),
    "nmap_full": KaliTool(
        "nmap", "recon", "approval_required",
        "Full TCP port scan with service/version detection.",
        "nmap", "-Pn -p- -sV -T4 {target}",
    ),
    "nmap_udp": KaliTool(
        "nmap", "recon", "approval_required",
        "UDP port scan (top 20 ports).",
        "nmap", "-sU --top-ports 20 {target}", requires_admin=True,
    ),
    "nmap_vuln": KaliTool(
        "nmap", "vuln", "approval_required",
        "Nmap vulnerability scripts against target.",
        "nmap", "-Pn --script vuln {target}",
    ),
    "ping_check": KaliTool(
        "ping", "recon", "safe_auto",
        "Check if target is reachable.",
        "ping", "-c 3 {target}",
    ),
    "netdiscover": KaliTool(
        "netdiscover", "recon", "approval_required",
        "ARP-based host discovery on local network.",
        "netdiscover", "-r {target}", requires_admin=True,
    ),
    "arp_scan": KaliTool(
        "arp-scan", "recon", "approval_required",
        "ARP scan local network for live hosts.",
        "arp-scan", "--localnet", requires_admin=True,
    ),
    "dmitry": KaliTool(
        "dmitry", "recon", "safe_auto",
        "Passive recon: WHOIS, netcraft, email harvesting.",
        "dmitry", "-winsepfb {target}",
    ),
    "dnsrecon": KaliTool(
        "dnsrecon", "recon", "safe_auto",
        "DNS enumeration: records, zone transfers, reverse lookups.",
        "dnsrecon", "-d {target}",
    ),
    "dnsenum": KaliTool(
        "dnsenum", "recon", "safe_auto",
        "DNS enumeration and brute-force of subdomains.",
        "dnsenum", "--enum {target}",
    ),
    "amass_passive": KaliTool(
        "amass", "recon", "safe_auto",
        "Passive subdomain enumeration via OSINT.",
        "amass", "enum -passive -d {target}",
    ),
    "subfinder": KaliTool(
        "subfinder", "recon", "safe_auto",
        "Fast passive subdomain discovery.",
        "subfinder", "-d {target}",
    ),
    "sublist3r": KaliTool(
        "sublist3r", "recon", "safe_auto",
        "Subdomain enumeration using search engines.",
        "sublist3r", "-d {target}",
    ),
    "assetfinder": KaliTool(
        "assetfinder", "recon", "safe_auto",
        "Find domains and subdomains related to a target.",
        "assetfinder", "--subs-only {target}",
    ),
    "theharvester": KaliTool(
        "theHarvester", "recon", "safe_auto",
        "Email, subdomain, IP, and URL harvesting via OSINT.",
        "theHarvester", "-d {target} -b all",
    ),
    "sherlock": KaliTool(
        "sherlock", "osint", "safe_auto",
        "Hunt down social media accounts by username.",
        "sherlock", "{target}",
    ),
    "metagoofil": KaliTool(
        "metagoofil", "osint", "safe_auto",
        "Extract metadata from public documents.",
        "metagoofil", "-d {target} -t pdf,doc,xls -l 20 -n 5 -o /tmp/metagoofil",
    ),
    "recon_ng": KaliTool(
        "recon-ng", "recon", "safe_auto",
        "Full-featured web reconnaissance framework.",
        "recon-ng", "",
    ),
    "spiderfoot": KaliTool(
        "spiderfoot", "recon", "safe_auto",
        "Automated OSINT collection across 200+ sources.",
        "spiderfoot", "-s {target} -q",
    ),
    "parsero": KaliTool(
        "parsero", "recon", "safe_auto",
        "Read robots.txt and test disallowed entries.",
        "parsero", "-u {target}",
    ),
    "maryam": KaliTool(
        "maryam", "recon", "safe_auto",
        "Open-source intelligence framework.",
        "maryam", "",
    ),

    # ── Web Scanning ───────────────────────────────────────────────────
    "whatweb": KaliTool(
        "whatweb", "web", "safe_auto",
        "Web technology fingerprinting.",
        "whatweb", "--no-errors {target}",
    ),
    "httpx_probe": KaliTool(
        "httpx", "web", "safe_auto",
        "HTTP probing — titles, status, technologies.",
        "httpx", "-silent -title -tech-detect -u {target}",
    ),
    "nuclei_safe": KaliTool(
        "nuclei", "vuln", "safe_auto",
        "Nuclei low-risk exposure and misconfiguration templates.",
        "nuclei", "-u {target} -severity info,low -tags tech,exposure,misconfig -jsonl",
    ),
    "nuclei_full": KaliTool(
        "nuclei", "vuln", "approval_required",
        "Nuclei full scan including medium/high severity.",
        "nuclei", "-u {target} -severity info,low,medium,high -jsonl",
    ),
    "nikto_scan": KaliTool(
        "nikto", "web", "approval_required",
        "Web server vulnerability scanner.",
        "nikto", "-h {target} -nointeractive",
    ),
    "gobuster_dir": KaliTool(
        "gobuster", "web", "approval_required",
        "Directory and file brute-force discovery.",
        "gobuster", "dir -u {target} -w /usr/share/wordlists/dirb/common.txt -q",
    ),
    "gobuster_dns": KaliTool(
        "gobuster", "recon", "approval_required",
        "DNS subdomain brute-force.",
        "gobuster", "dns -d {target} -w /usr/share/wordlists/dnsmap.txt -q",
    ),
    "ffuf_fuzz": KaliTool(
        "ffuf", "web", "approval_required",
        "Web path and parameter fuzzing.",
        "ffuf", "-u {target}/FUZZ -w /usr/share/wordlists/dirb/common.txt -mc 200,204,301,302,403 -s",
    ),
    "dirb": KaliTool(
        "dirb", "web", "approval_required",
        "Web content scanner using wordlists.",
        "dirb", "{target}",
    ),
    "dirbuster": KaliTool(
        "dirbuster", "web", "approval_required",
        "GUI-based web directory and file brute-forcer.",
        "dirbuster", "",
    ),
    "dirsearch": KaliTool(
        "dirsearch", "web", "approval_required",
        "Web path scanner with recursion support.",
        "dirsearch", "-u {target} -q",
    ),
    "feroxbuster": KaliTool(
        "feroxbuster", "web", "approval_required",
        "Recursive web content discovery tool.",
        "feroxbuster", "-u {target} -q --no-recursion",
    ),
    "wpscan": KaliTool(
        "wpscan", "web", "approval_required",
        "WordPress vulnerability scanner.",
        "wpscan", "--url {target} --enumerate",
    ),
    "burpsuite": KaliTool(
        "burpsuite", "web", "approval_required",
        "Web application security testing platform (GUI).",
        "burpsuite", "",
    ),
    "caido": KaliTool(
        "caido", "web", "approval_required",
        "Web security auditing tool.",
        "caido", "",
    ),
    "arjun": KaliTool(
        "arjun", "web", "approval_required",
        "HTTP parameter discovery.",
        "arjun", "-u {target}",
    ),
    "sstimap": KaliTool(
        "sstimap", "web", "approval_required",
        "Server-side template injection detection and exploitation.",
        "sstimap", "-u {target}",
    ),

    # ── Exploitation ───────────────────────────────────────────────────
    "msfconsole": KaliTool(
        "msfconsole", "exploit", "lab_or_manual",
        "Metasploit Framework interactive console.",
        "msfconsole", "",
    ),
    "msfvenom": KaliTool(
        "msfvenom", "exploit", "lab_or_manual",
        "Payload generation and encoding.",
        "msfvenom", "-l payloads",
    ),
    "armitage": KaliTool(
        "armitage", "exploit", "lab_or_manual",
        "GUI cyber attack management for Metasploit.",
        "armitage", "",
    ),
    "beef_xss": KaliTool(
        "beef-xss", "exploit", "lab_or_manual",
        "Browser exploitation framework.",
        "beef-xss", "",
    ),
    "evil_winrm": KaliTool(
        "evil-winrm", "exploit", "approval_required",
        "WinRM shell for pentesting Windows.",
        "evil-winrm", "-i {target}",
    ),
    "ligolo_ng": KaliTool(
        "ligolo-ng", "exploit", "lab_or_manual",
        "Advanced tunneling/pivoting tool.",
        "ligolo-ng", "",
    ),
    "hoaxshell": KaliTool(
        "hoaxshell", "exploit", "lab_or_manual",
        "Unconventional reverse shell payload generator.",
        "hoaxshell", "",
    ),
    "chisel": KaliTool(
        "chisel", "exploit", "lab_or_manual",
        "Fast TCP/UDP tunnel over HTTP.",
        "chisel", "",
    ),

    # ── Credential / Password ──────────────────────────────────────────
    "hydra_brute": KaliTool(
        "hydra", "credentials", "credential_approval",
        "Online password brute-force for many protocols.",
        "hydra", "-L /usr/share/wordlists/metasploit/unix_users.txt -P /usr/share/wordlists/metasploit/unix_passwords.txt -t 4 ssh://{target}",
    ),
    "medusa": KaliTool(
        "medusa", "credentials", "credential_approval",
        "Parallel network login brute-forcer.",
        "medusa", "-h {target} -U /usr/share/wordlists/metasploit/unix_users.txt -P /usr/share/wordlists/metasploit/unix_passwords.txt -M ssh",
    ),
    "john_crack": KaliTool(
        "john", "credentials", "approval_required",
        "Offline password hash cracker.",
        "john", "--wordlist=/usr/share/wordlists/rockyou.txt {target}",
    ),
    "hashcat": KaliTool(
        "hashcat", "credentials", "approval_required",
        "GPU-accelerated password hash recovery.",
        "hashcat", "-a 0 -m 0 {target} /usr/share/wordlists/rockyou.txt",
    ),
    "rainbowcrack": KaliTool(
        "rcrack", "credentials", "approval_required",
        "Rainbow table-based hash cracking.",
        "rcrack", ".",
    ),
    "crunch": KaliTool(
        "crunch", "credentials", "safe_auto",
        "Custom wordlist generator.",
        "crunch", "8 8 abcdefghijklmnopqrstuvwxyz0123456789",
    ),
    "cewl": KaliTool(
        "cewl", "credentials", "safe_auto",
        "Custom wordlist generator from website content.",
        "cewl", "{target}",
    ),
    "hashid": KaliTool(
        "hashid", "credentials", "safe_auto",
        "Identify hash types.",
        "hashid", "{target}",
    ),
    "kerberoast": KaliTool(
        "kerberoast", "credentials", "approval_required",
        "Kerberoasting attack tools for Active Directory.",
        "python3 /usr/share/kerberoast/tgsrepcrack.py", "/usr/share/wordlists/rockyou.txt {target}",
    ),

    # ── SQL Injection ──────────────────────────────────────────────────
    "sqlmap_safe": KaliTool(
        "sqlmap", "web", "approval_required",
        "Automated SQL injection detection (conservative).",
        "sqlmap", "-u {target} --batch --risk=1 --level=1 --smart",
    ),
    "sqlmap_full": KaliTool(
        "sqlmap", "web", "approval_required",
        "Automated SQL injection detection and exploitation.",
        "sqlmap", "-u {target} --batch --risk=3 --level=5",
    ),
    "sqlsus": KaliTool(
        "sqlsus", "web", "approval_required",
        "MySQL injection and takeover tool.",
        "sqlsus", "",
    ),

    # ── Network / MITM ─────────────────────────────────────────────────
    "ettercap": KaliTool(
        "ettercap", "network", "approval_required",
        "MITM attacks, sniffing, and protocol dissection.",
        "ettercap", "-T -q -i eth0",
        requires_admin=True,
    ),
    "bettercap": KaliTool(
        "bettercap", "network", "approval_required",
        "Network attack and monitoring framework.",
        "bettercap", "",
        requires_admin=True,
    ),
    "responder": KaliTool(
        "responder", "network", "approval_required",
        "LLMNR/NTB-NS/MDNS poisoner and credential capture.",
        "responder", "-I eth0 -rdw",
        requires_admin=True,
    ),
    "mitm6": KaliTool(
        "mitm6", "network", "approval_required",
        "IPv6 MITM attack tool.",
        "mitm6", "-d {target}",
        requires_admin=True,
    ),
    "dsniff": KaliTool(
        "dsniff", "network", "approval_required",
        "Network sniffing and credential capture.",
        "dsniff", "",
        requires_admin=True,
    ),
    "scapy": KaliTool(
        "scapy", "network", "approval_required",
        "Interactive packet manipulation and analysis.",
        "scapy", "",
    ),
    "hping3": KaliTool(
        "hping3", "network", "approval_required",
        "TCP/IP packet assembler and analyzer.",
        "hping3", "-S -p 80 {target}",
        requires_admin=True,
    ),
    "tcpdump": KaliTool(
        "tcpdump", "network", "approval_required",
        "Packet capture and analysis.",
        "tcpdump", "-i eth0 host {target} -c 100",
        requires_admin=True,
    ),
    "netcat": KaliTool(
        "nc", "network", "approval_required",
        "TCP/UDP network utility — banner grabbing.",
        "nc", "-nv {target} 80",
    ),
    "yersinia": KaliTool(
        "yersinia", "network", "approval_required",
        "Layer 2 protocol attack framework.",
        "yersinia", "-I",
        requires_admin=True,
    ),
    "goldeneye": KaliTool(
        "goldeneye", "network", "approval_required",
        "HTTP DoS test tool for authorized load testing.",
        "goldeneye", "{target}",
    ),

    # ── WiFi ───────────────────────────────────────────────────────────
    "aircrack_ng": KaliTool(
        "aircrack-ng", "wifi", "approval_required",
        "WiFi network security auditing suite.",
        "aircrack-ng", "",
        requires_admin=True,
    ),
    "wifite": KaliTool(
        "wifite", "wifi", "approval_required",
        "Automated wireless auditing tool.",
        "wifite", "",
        requires_admin=True,
    ),
    "reaver": KaliTool(
        "reaver", "wifi", "approval_required",
        "WPS brute-force attack tool.",
        "reaver", "-i wlan0 -b {target} -vv",
        requires_admin=True,
    ),
    "fluxion": KaliTool(
        "fluxion", "wifi", "approval_required",
        "Evil twin WiFi attack framework.",
        "fluxion", "",
        requires_admin=True,
    ),
    "kismet": KaliTool(
        "kismet", "wifi", "approval_required",
        "Wireless network detector, sniffer, IDS.",
        "kismet", "",
        requires_admin=True,
    ),
    "wifiphisher": KaliTool(
        "wifiphisher", "wifi", "approval_required",
        "Phishing framework for WiFi credential capture.",
        "wifiphisher", "",
        requires_admin=True,
    ),
    "fern_wifi_cracker": KaliTool(
        "fern-wifi-cracker", "wifi", "approval_required",
        "GUI WiFi auditing and cracking tool.",
        "fern-wifi-cracker", "",
        requires_admin=True,
    ),
    "cowpatty": KaliTool(
        "cowpatty", "wifi", "approval_required",
        "WPA-PSK dictionary attack.",
        "cowpatty", "-r {target} -f /usr/share/wordlists/rockyou.txt -s target_ssid",
    ),
    "macchanger": KaliTool(
        "macchanger", "wifi", "approval_required",
        "Change or spoof MAC address.",
        "macchanger", "--random eth0",
        requires_admin=True,
    ),
    "airgeddon": KaliTool(
        "airgeddon", "wifi", "approval_required",
        "Multi-use wireless auditing framework.",
        "airgeddon", "",
        requires_admin=True,
    ),

    # ── Active Directory / Windows ─────────────────────────────────────
    "bloodhound": KaliTool(
        "bloodhound", "ad", "approval_required",
        "Active Directory attack path mapper.",
        "bloodhound", "",
    ),
    "crackmapexec": KaliTool(
        "crackmapexec", "ad", "approval_required",
        "Swiss army knife for Active Directory pentesting.",
        "crackmapexec", "smb {target}",
    ),
    "netexec": KaliTool(
        "netexec", "ad", "approval_required",
        "Network service execution and enumeration (CrackMapExec successor).",
        "netexec", "smb {target}",
    ),
    "enum4linux": KaliTool(
        "enum4linux", "ad", "approval_required",
        "SMB/SAMBA enumeration for Windows/Linux.",
        "enum4linux", "-a {target}",
    ),
    "mimikatz": KaliTool(
        "mimikatz", "ad", "lab_or_manual",
        "Windows credential extraction (lab use).",
        "mimikatz", "",
    ),
    "impacket_secretsdump": KaliTool(
        "impacket-secretsdump", "ad", "approval_required",
        "Dump hashes and secrets from Windows systems.",
        "impacket-secretsdump", "{target}",
    ),
    "impacket_psexec": KaliTool(
        "impacket-psexec", "ad", "approval_required",
        "Remote command execution via SMB.",
        "impacket-psexec", "{target}",
    ),
    "impacket_getuserspns": KaliTool(
        "impacket-GetUserSPNs", "ad", "approval_required",
        "Kerberoasting — enumerate and request service tickets.",
        "impacket-GetUserSPNs", "{target}",
    ),
    "smtp_user_enum": KaliTool(
        "smtp-user-enum", "recon", "approval_required",
        "SMTP user enumeration via VRFY/EXPN/RCPT.",
        "smtp-user-enum", "-M VRFY -U /usr/share/wordlists/metasploit/unix_users.txt -t {target}",
    ),

    # ── Forensics / Analysis ───────────────────────────────────────────
    "autopsy": KaliTool(
        "autopsy", "forensics", "safe_auto",
        "Digital forensics platform (GUI).",
        "autopsy", "",
    ),
    "binwalk": KaliTool(
        "binwalk", "forensics", "safe_auto",
        "Firmware analysis and extraction.",
        "binwalk", "{target}",
    ),
    "bulk_extractor": KaliTool(
        "bulk_extractor", "forensics", "safe_auto",
        "Extract forensic data from disk images.",
        "bulk_extractor", "-o /tmp/bulk_out {target}",
    ),
    "steghide": KaliTool(
        "steghide", "forensics", "safe_auto",
        "Steganography — embed/extract data from files.",
        "steghide", "info {target}",
    ),
    "ghidra": KaliTool(
        "ghidra", "forensics", "safe_auto",
        "NSA reverse engineering framework (GUI).",
        "ghidra", "",
    ),
    "jadx": KaliTool(
        "jadx", "forensics", "safe_auto",
        "Dex/APK to Java decompiler.",
        "jadx", "{target}",
    ),
    "apktool": KaliTool(
        "apktool", "forensics", "safe_auto",
        "Android APK reverse engineering.",
        "apktool", "d {target}",
    ),
    "yara": KaliTool(
        "yara", "forensics", "safe_auto",
        "Malware identification via pattern matching.",
        "yara", "/usr/share/yara-rules/ {target}",
    ),
    "tiger": KaliTool(
        "tiger", "forensics", "safe_auto",
        "Unix security audit and intrusion detection.",
        "tiger", "",
    ),
    "pspy": KaliTool(
        "pspy", "forensics", "safe_auto",
        "Monitor running processes without root.",
        "pspy", "",
    ),

    # ── Social Engineering ─────────────────────────────────────────────
    "setoolkit": KaliTool(
        "setoolkit", "social_eng", "approval_required",
        "Social Engineering Toolkit — phishing, credential harvest, payloads.",
        "setoolkit", "",
    ),
    "maltego": KaliTool(
        "maltego", "osint", "safe_auto",
        "OSINT and link analysis platform (GUI).",
        "maltego", "",
    ),

    # ── IDS / Monitoring ───────────────────────────────────────────────
    "snort": KaliTool(
        "snort", "ids", "approval_required",
        "Network intrusion detection system.",
        "snort", "-A console -i eth0",
        requires_admin=True,
    ),
    "legion": KaliTool(
        "legion", "recon", "approval_required",
        "Semi-automated network penetration testing framework.",
        "legion", "",
    ),
    "autorecon": KaliTool(
        "autorecon", "recon", "approval_required",
        "Multi-threaded network recon tool.",
        "autorecon", "{target}",
    ),
    "veil": KaliTool(
        "veil", "exploit", "lab_or_manual",
        "AV-evasion payload generator.",
        "veil", "",
    ),
    "tinja": KaliTool(
        "tinja", "web", "approval_required",
        "Template injection detection.",
        "tinja", "url -u {target}",
    ),
    "hexstrike_ai": KaliTool(
        "hexstrike-ai", "recon", "safe_auto",
        "AI-assisted penetration testing assistant.",
        "hexstrike-ai", "",
    ),
}


# ── Category groupings for autonomous goal selection ──────────────────
GOAL_TOOLSETS: dict[str, list[str]] = {
    "recon": [
        "ping_check", "nmap_top_ports", "whatweb", "httpx_probe",
        "dnsrecon", "dnsenum", "amass_passive", "subfinder", "theharvester",
    ],
    "web audit": [
        "whatweb", "httpx_probe", "nuclei_safe", "nuclei_full",
        "nikto_scan", "gobuster_dir", "dirb", "dirsearch", "feroxbuster",
        "wpscan", "arjun", "ffuf_fuzz",
    ],
    "vulnerability scan": [
        "nuclei_safe", "nuclei_full", "nikto_scan", "nmap_vuln",
        "sstimap", "tinja",
    ],
    "full pentest": list(TOOLS.keys()),
    "wifi": [
        "aircrack_ng", "wifite", "reaver", "kismet", "airgeddon",
        "wifiphisher", "cowpatty",
    ],
    "active directory": [
        "enum4linux", "bloodhound", "crackmapexec", "netexec",
        "impacket_getuserspns", "impacket_secretsdump",
        "responder", "mitm6",
    ],
    "credentials": [
        "hydra_brute", "medusa", "john_crack", "hashcat", "cewl",
    ],
    "osint": [
        "theharvester", "sherlock", "spiderfoot", "maltego",
        "dmitry", "recon_ng", "metagoofil", "sublist3r",
    ],
    "forensics": [
        "binwalk", "bulk_extractor", "steghide", "autopsy", "yara",
        "jadx", "apktool", "ghidra",
    ],
}


def explain_tool(name: str) -> str | None:
    tool = TOOLS.get(name)
    if not tool:
        # Try matching by command name
        for action, t in TOOLS.items():
            if t.command.split()[0] == name or action == name:
                tool = t
                break
    if not tool:
        return None
    return (
        f"{tool.command}: {tool.summary}\n"
        f"Category: {tool.category}  |  Risk: {tool.risk}\n"
        f"Example: {tool.command} {tool.args_template.replace('{target}', 'TARGET')}"
    )


def recommend_tools(task: str) -> list[KaliTool]:
    text = task.lower()
    if any(w in text for w in ("web", "website", "http", "url", "wordpress")):
        keys = ["whatweb", "httpx_probe", "nuclei_safe", "nikto_scan", "gobuster_dir"]
    elif any(w in text for w in ("wifi", "wireless", "wpa", "wep")):
        keys = ["aircrack_ng", "wifite", "kismet", "reaver"]
    elif any(w in text for w in ("password", "credential", "login", "brute")):
        keys = ["hydra_brute", "john_crack", "hashcat", "medusa"]
    elif any(w in text for w in ("exploit", "vulnerability", "cve", "metasploit")):
        keys = ["nmap_vuln", "nuclei_full", "nikto_scan", "msfconsole"]
    elif any(w in text for w in ("active directory", "ad", "smb", "windows", "kerberos")):
        keys = ["enum4linux", "crackmapexec", "bloodhound", "impacket_getuserspns"]
    elif any(w in text for w in ("osint", "recon", "subdomain", "dns")):
        keys = ["amass_passive", "subfinder", "theharvester", "dnsrecon"]
    elif any(w in text for w in ("forensic", "malware", "binary", "apk")):
        keys = ["binwalk", "yara", "jadx", "ghidra"]
    else:
        keys = ["nmap_top_ports", "whatweb", "httpx_probe", "nuclei_safe"]
    return [TOOLS[k] for k in keys if k in TOOLS]
