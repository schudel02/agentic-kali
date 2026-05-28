from pathlib import Path


def test_postinst_preserves_existing_config():
    postinst = Path("debian/DEBIAN/postinst").read_text(encoding="utf-8")
    assert "if [ ! -f /etc/agentic-kali/config.json ]" in postinst
    assert "Keeping existing /etc/agentic-kali/config.json" in postinst
    assert "/etc/agentic-kali/admin.json" in postinst
    assert "chmod 0660 /etc/agentic-kali/scope.json" in postinst
