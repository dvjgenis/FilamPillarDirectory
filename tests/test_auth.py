"""Tests for email + password + OTP authentication."""

from __future__ import annotations

import time

import auth


def test_admin_navigation_labels():
    assert len(auth.ADMIN_PAGE_LABELS) == 4
    assert auth.ADMIN_PAGE_LABELS[0] == "👥 Directory"


def test_is_admin_page():
    assert auth.is_admin_page("👥 Directory") is True
    assert auth.is_admin_page("📊 Overview") is False


def test_auth_from_toml_reads_emails_and_password():
    config = {
        "credentials": {
            "usernames": {
                "filpilchurch": {
                    "email1": "a@example.com",
                    "email2": "B@Example.com",
                    "email3": "c@example.com",
                    "password": "secret",
                }
            }
        },
        "Gmail App Password": {"app_password": "abcd efgh"},
    }
    parsed = auth._auth_from_toml(config)
    assert parsed is not None
    assert parsed["emails"] == ["a@example.com", "b@example.com", "c@example.com"]
    assert parsed["password"] == "secret"
    assert parsed["smtp_app_password"] == "abcdefgh"


def test_verify_password_allowlist():
    cfg = {
        "emails": ["staff@example.com"],
        "password": "shared",
        "smtp_user": "sender@gmail.com",
        "smtp_app_password": "",
    }
    assert auth.verify_password("staff@example.com", "shared", cfg) is True
    assert auth.verify_password("other@example.com", "shared", cfg) is False
    assert auth.verify_password("staff@example.com", "wrong", cfg) is False


def test_otp_verify_roundtrip(monkeypatch):
    class FakeSession(dict):
        pass

    state = FakeSession()
    monkeypatch.setattr(auth.st, "session_state", state, raising=False)

    auth.store_otp_in_session("staff@example.com", "123456")
    assert auth.verify_otp("staff@example.com", "123456") is True
    assert auth.verify_otp("staff@example.com", "000000") is False


def test_otp_expires(monkeypatch):
    class FakeSession(dict):
        pass

    state = FakeSession()
    monkeypatch.setattr(auth.st, "session_state", state, raising=False)

    auth.store_otp_in_session("staff@example.com", "123456")
    state[auth.SESSION_OTP_EXPIRES_KEY] = time.time() - 1
    assert auth.verify_otp("staff@example.com", "123456") is False


def test_credentials_missing_without_file(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "CREDENTIALS_PATH", tmp_path / "missing.toml")
    monkeypatch.setattr(auth, "SAMPLE_CREDENTIALS_PATH", tmp_path / "missing_sample.toml")
    monkeypatch.setattr(auth, "_auth_from_secrets", lambda: None)
    assert auth.credentials_missing() is True
