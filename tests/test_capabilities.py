from agentic_kali.tools.capabilities import capability_menu, find_capability


def test_capability_menu_lists_recon():
    assert "Quick Recon" in capability_menu()


def test_find_capability_by_key():
    item = find_capability("use quick_recon")
    assert item
    assert item.title == "Quick Recon"

