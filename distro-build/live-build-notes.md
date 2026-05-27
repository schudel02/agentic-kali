# Kali Live Build Notes

Use this inside a Kali build VM.

```bash
sudo apt update
sudo apt install -y git live-build cdebootstrap devscripts
git clone https://gitlab.com/kalilinux/build-scripts/live-build-config.git
cd live-build-config
```

Or run the scaffold:

```bash
sudo bash distro-build/build-iso.sh
```

Default service behavior is oneshot. It does not run without `/etc/agentic-kali/scope.json`.
