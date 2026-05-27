# Distro Build

Planned Kali packaging path:

1. Build in a VM or CI runner with `live-build`.
2. Add package manifest from `packages.txt`.
3. Install `agentic-kali` as a local Python package.
4. Enable the agent UI/service only after first-run scope setup.

No offensive automation should run on boot.

## Files

- `packages.txt`: Kali packages
- `install-agent.sh`: installs the Python agent to `/opt/agentic-kali`
- `systemd/agentic-kali.service`: oneshot CLI service
- `systemd/agentic-kali-ui.service`: local web UI service
- `live-build-notes.md`: ISO build notes
- `build-iso.sh`: repeatable Kali ISO build scaffold
- `README-build.md`: build usage
