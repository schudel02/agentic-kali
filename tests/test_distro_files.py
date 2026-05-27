from pathlib import Path


def test_distro_build_files_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "distro-build" / "build-iso.sh").exists()
    assert (root / "distro-build" / "build-deb.sh").exists()
    assert (root / "distro-build" / "install-agent.sh").exists()
    assert (root / "distro-build" / "systemd" / "agentic-kali-ui.service").exists()
    assert (root / "distro-build" / "systemd" / "agentic-kali-gui.desktop").exists()
    assert (root / "debian" / "DEBIAN" / "control").exists()
    assert (root / "debian" / "DEBIAN" / "templates").exists()
    assert (root / "debian" / "DEBIAN" / "config").exists()
    assert (root / "LICENSE").exists()
