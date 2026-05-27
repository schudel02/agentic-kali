#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${WORK_DIR:-$ROOT_DIR/.build/kali-live}"
LIVE_REPO="https://gitlab.com/kalilinux/build-scripts/live-build-config.git"

command -v git >/dev/null
command -v lb >/dev/null

mkdir -p "$(dirname "$WORK_DIR")"

if [ ! -d "$WORK_DIR/.git" ]; then
  git clone "$LIVE_REPO" "$WORK_DIR"
fi

cd "$WORK_DIR"
git pull --ff-only

PACKAGE_FILE="kali-config/variant-default/package-lists/agentic-kali.list.chroot"
HOOK_DIR="kali-config/common/hooks/live"
HOOK_FILE="$HOOK_DIR/agentic-kali.chroot"
INCLUDE_DIR="config/includes.chroot/opt/agentic-kali"

mkdir -p "$(dirname "$PACKAGE_FILE")" "$HOOK_DIR" "$INCLUDE_DIR"
cp "$ROOT_DIR/distro-build/packages.txt" "$PACKAGE_FILE"
rsync -a --delete \
  --exclude .git \
  --exclude .build \
  --exclude .venv \
  --exclude __pycache__ \
  "$ROOT_DIR/" "$INCLUDE_DIR/"

cat > "$HOOK_FILE" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /opt/agentic-kali
bash distro-build/install-agent.sh
EOF
chmod +x "$HOOK_FILE"

./build.sh --variant default --verbose

