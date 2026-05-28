from __future__ import annotations

import re
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path


LAB_ROOT = Path.home() / ".agentic-kali" / "labs" / "basic-web"


@dataclass(frozen=True)
class LabRequest:
    kind: str = "basic-web"
    port: int = 0


@dataclass(frozen=True)
class LabServer:
    url: str
    path: Path
    process: subprocess.Popen


def parse_lab_request(text: str) -> LabRequest | None:
    lowered = text.lower()
    if not any(phrase in lowered for phrase in ("local test server", "test server", "local lab", "practice server", "lab server")):
        return None
    if not any(word in lowered for word in ("create", "start", "spin up", "make", "launch", "run")):
        return None
    port_match = re.search(r"\bport\s+(\d{2,5})\b", lowered)
    port = int(port_match.group(1)) if port_match else 0
    return LabRequest(port=port)


def start_lab_server(request: LabRequest | None = None) -> LabServer:
    request = request or LabRequest()
    _write_basic_web_lab(LAB_ROOT)
    port = request.port or _free_port()
    python = shutil.which("python3") or shutil.which("python")
    if not python:
        raise RuntimeError("python3 is required to start a local lab server")
    process = subprocess.Popen(
        [python, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(LAB_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return LabServer(url=f"http://127.0.0.1:{port}", path=LAB_ROOT, process=process)


def _write_basic_web_lab(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "index.html").write_text(
        """<!doctype html>
<html>
<head>
  <title>Agent Kal Local Lab</title>
  <script src="/assets/app.js"></script>
</head>
<body>
  <h1>Agent Kal Local Lab</h1>
  <p>This is a safe local practice target for recon and web fingerprinting.</p>
  <a href="/admin.html">Admin area placeholder</a>
</body>
</html>
""",
        encoding="utf-8",
    )
    (path / "admin.html").write_text(
        "<!doctype html><title>Admin Placeholder</title><h1>Admin Placeholder</h1><p>No real credentials live here.</p>\n",
        encoding="utf-8",
    )
    (path / "robots.txt").write_text("User-agent: *\nDisallow: /admin.html\n", encoding="utf-8")
    assets = path / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "app.js").write_text("console.log('Agent Kal local lab loaded');\n", encoding="utf-8")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
