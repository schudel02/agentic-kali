from agentic_kali.policy.admin import is_admin_phrase, phrase_hash


def test_phrase_hash_matches_phrase(tmp_path):
    path = tmp_path / "admin.json"
    path.write_text('{"admin_phrase_sha256": "' + phrase_hash("secret") + '"}', encoding="utf-8")
    assert is_admin_phrase("secret", path)
    assert not is_admin_phrase("wrong", path)

