"""Tests for data source selection."""

from __future__ import annotations

import data_source


def test_uses_csv_by_default(monkeypatch):
    monkeypatch.delenv("CHURCH_DATA_SOURCE", raising=False)
    monkeypatch.delenv("CHURCH_SHEET_ID", raising=False)
    assert data_source.uses_google_sheets() is False


def test_uses_sheets_when_env_set(monkeypatch):
    monkeypatch.setenv("CHURCH_DATA_SOURCE", "sheets")
    monkeypatch.setenv("CHURCH_SHEET_ID", "abc123")
    assert data_source.uses_google_sheets() is True


def test_forces_csv_when_env_set(monkeypatch):
    monkeypatch.setenv("CHURCH_DATA_SOURCE", "csv")
    monkeypatch.setenv("CHURCH_SHEET_ID", "abc123")
    assert data_source.uses_google_sheets() is False
