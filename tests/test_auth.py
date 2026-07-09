"""Tests for auth navigation helpers."""

from __future__ import annotations

from types import SimpleNamespace

import auth


def test_public_navigation_labels():
    assert len(auth.PUBLIC_PAGE_LABELS) == 4
    assert auth.PUBLIC_PAGE_LABELS[0] == "📊 Overview"


def test_admin_navigation_labels():
    assert len(auth.ADMIN_PAGE_LABELS) == 4
    assert auth.ADMIN_PAGE_LABELS[0] == "👥 Directory"


def test_admin_pages_when_authenticated(monkeypatch):
    monkeypatch.setattr(auth, "is_admin_authenticated", lambda: True)
    options = auth.navigation_options()
    assert len(options) == 4
    assert options == auth.ADMIN_PAGE_LABELS
    assert auth.PUBLIC_PAGE_LABELS[0] not in options


def test_is_admin_page():
    assert auth.is_admin_page("👥 Directory") is True
    assert auth.is_admin_page("📊 Overview") is False


def test_normalize_credentials_lowercases_and_deep_copies():
    nested = SimpleNamespace(
        items=lambda: [
            (
                "usernames",
                SimpleNamespace(
                    items=lambda: [
                        (
                            "FilPilChurch",
                            SimpleNamespace(
                                items=lambda: [
                                    ("email", "a@b.c"),
                                    ("name", "Staff"),
                                    ("password", "$2b$12$abc"),
                                ]
                            ),
                        )
                    ]
                ),
            )
        ]
    )
    # Prefer plain dict path (AttrDict-like nested mappings)
    raw = {
        "usernames": {
            "FilPilChurch": {
                "email": "a@b.c",
                "name": "Staff",
                "password": "$2b$12$abc",
            }
        }
    }
    normalized = auth._normalize_credentials(raw)
    assert list(normalized["usernames"].keys()) == ["filpilchurch"]
    user = normalized["usernames"]["filpilchurch"]
    assert user["email"] == "a@b.c"
    user["failed_login_attempts"] = 0  # must be mutable
    assert user["failed_login_attempts"] == 0
