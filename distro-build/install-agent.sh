#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/agentic-kali"
VENV_DIR="$APP_DIR/.venv"

install -d "$APP_DIR"
cp -R src pyproject.toml README.md examples "$APP_DIR/"

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -e "$APP_DIR"

install -Dm0644 distro-build/systemd/agentic-kali.service /etc/systemd/system/agentic-kali.service
install -Dm0644 distro-build/systemd/agentic-kali-ui.service /etc/systemd/system/agentic-kali-ui.service
install -Dm0644 distro-build/systemd/agentic-kali-gui.desktop /usr/share/applications/agentic-kali-gui.desktop
systemctl daemon-reload

echo "Installed agentic-kali to $APP_DIR"
echo "Run: agentic-kali init /etc/agentic-kali/scope.json"
echo "UI:  systemctl enable --now agentic-kali-ui"
