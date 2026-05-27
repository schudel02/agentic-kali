# ISO Build

Run inside Kali:

```bash
sudo apt update
sudo apt install -y git live-build cdebootstrap devscripts rsync
sudo bash distro-build/build-iso.sh
```

Output is produced by Kali `live-build-config` under `.build/kali-live`.

The agent is copied into `/opt/agentic-kali` and installed by a chroot hook.

