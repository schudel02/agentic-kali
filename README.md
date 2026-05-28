# Agentic Kali

Authorized AI-assisted penetration testing distribution skeleton.

## Components

- `agent-core`: task planning and run orchestration
- `policy-gate`: target scope, permission, and action safety checks
- `tool-runners`: controlled wrappers for security tools
- `evidence-store`: logs, artifacts, and findings
- `reporting`: report generation
- `ai`: constrained planning interface
- `distro-build`: Kali image build notes and package manifest

## Safety Model

The system requires explicit scope before any action:

- authorized targets
- allowed actions
- test window
- intensity level
- approval mode

Intrusive actions are blocked by default.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m agentic_kali.cli examples/scope.local.json
```

Create a new scope file:

```powershell
python -m agentic_kali.cli init examples/my-scope.json
```

## Current Safe Actions

- `ping_check`: policy execution test
- `nmap_top_ports`: top 100 TCP ports with service detection
- `whatweb`: web fingerprinting
- `httpx_probe`: HTTP title and tech detection
- `nuclei_safe`: nuclei info/low severity templates with limited tags

All actions require target scope approval before execution.

## Output

Runs write JSON and Markdown reports to `reports/`.

Findings are severity-ranked from parsed metadata.

## Kali Install

```bash
sudo bash distro-build/install-agent.sh
sudo mkdir -p /etc/agentic-kali
agentic-kali init /etc/agentic-kali/scope.json
sudo systemctl start agentic-kali
sudo systemctl enable --now agentic-kali-ui
```

## Debian Package

Build on Linux:

```bash
sudo apt install -y dpkg-dev
bash distro-build/build-deb.sh
sudo apt install ./dist/agentic-kali_0.1.0_all.deb
```

The Debian installer prompts for authorized-use terms and Azure OpenAI configuration.

## Web UI Optional

```bash
python -m agentic_kali.ui
```

Open `http://127.0.0.1:8765`.

## Floating GUI

```bash
python -m agentic_kali.gui
```

Uses `/etc/agentic-kali/scope.json`.

The preview window shows activity events, policy decisions, selected actions, and tool output summaries.
Settings can be configured inside the floating GUI.
Agent Kal uses Azure AI for conversational replies when configured.

Watch Mode uses `xdotool` and `wmctrl` to preview desktop automation steps.

## Docker

```bash
docker compose up --build
```

## ISO Build

```bash
sudo bash distro-build/build-iso.sh
```

## Optional AI Provider

Set:

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4.1-mini
```

The provider can only request allowlisted safe actions.

Public targets are blocked unless `public_targets_allowed` is true in scope.

Azure OpenAI:

```bash
export AZURE_OPENAI_ENDPOINT="https://YOUR-RESOURCE.openai.azure.com"
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_DEPLOYMENT="your-model-deployment"
export AZURE_OPENAI_API_VERSION="2025-04-01-preview"
```

Or save these in `/etc/agentic-kali/config.json`.

Wizard:

```bash
sudo agentic-kali config
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

CI runs the same test suite with GitHub Actions.
