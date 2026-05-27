from agentic_kali.policy.targets import is_public_target


def test_loopback_not_public():
    assert not is_public_target("127.0.0.1")


def test_private_not_public():
    assert not is_public_target("192.168.1.10")


def test_public_ip_is_public():
    assert is_public_target("8.8.8.8")


def test_domain_is_public():
    assert is_public_target("https://example.com")
