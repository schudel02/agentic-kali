#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/.build/deb"
PKG_DIR="$BUILD_DIR/agentic-kali"
OUT_DIR="$ROOT_DIR/dist"

rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/opt/agentic-kali" \
  "$PKG_DIR/etc/systemd/system" \
  "$PKG_DIR/usr/share/applications" \
  "$PKG_DIR/DEBIAN" \
  "$OUT_DIR"

cp -R "$ROOT_DIR/src" "$ROOT_DIR/examples" "$ROOT_DIR/pyproject.toml" "$ROOT_DIR/README.md" "$PKG_DIR/opt/agentic-kali/"
cp "$ROOT_DIR/distro-build/systemd/agentic-kali.service" "$PKG_DIR/etc/systemd/system/"
cp "$ROOT_DIR/distro-build/systemd/agentic-kali-ui.service" "$PKG_DIR/etc/systemd/system/"
cp "$ROOT_DIR/distro-build/systemd/agentic-kali-gui.desktop" "$PKG_DIR/usr/share/applications/"
cp "$ROOT_DIR/debian/DEBIAN/"* "$PKG_DIR/DEBIAN/"
cp "$ROOT_DIR/LICENSE" "$PKG_DIR/opt/agentic-kali/"
chmod 0755 "$PKG_DIR/DEBIAN/postinst" "$PKG_DIR/DEBIAN/prerm" "$PKG_DIR/DEBIAN/postrm" "$PKG_DIR/DEBIAN/config"

dpkg-deb --build "$PKG_DIR" "$OUT_DIR/agentic-kali_0.1.0_all.deb"
