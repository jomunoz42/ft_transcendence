"""Tests for password hashing (auth ticket 01).

Pure function tests: no database. They only call the two public functions,
hash_password and verify_password, the way the rest of auth will.
"""

from app.auth.passwords import hash_password, verify_password


def test_same_password_hashed_twice_gives_different_hashes():
    assert hash_password("hunter22") != hash_password("hunter22")


def test_right_password_verifies():
    assert verify_password("hunter22", hash_password("hunter22")) is True


def test_wrong_password_does_not_verify():
    assert verify_password("hunter23", hash_password("hunter22")) is False


def test_hash_does_not_contain_the_plain_password():
    assert "hunter22" not in hash_password("hunter22")


def test_malformed_hash_does_not_verify():
    assert verify_password("hunter22", "not-a-real-hash") is False
    assert verify_password("hunter22", "") is False


def test_hash_uses_argon2id():
    assert hash_password("hunter22").startswith("$argon2id$")


def test_non_ascii_password_round_trips():
    stored = hash_password("pão-de-açúcar 🎵")
    assert verify_password("pão-de-açúcar 🎵", stored) is True
    assert verify_password("pao-de-acucar 🎵", stored) is False
