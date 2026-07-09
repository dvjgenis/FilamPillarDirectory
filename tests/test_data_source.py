"""Tests for data source selection."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import data_source
import pytest


def test_uses_csv_by_default(monkeypatch):
    monkeypatch.delenv("CHURCH_DATA_SOURCE", raising=False)
    monkeypatch.delenv("CHURCH_SHEET_ID", raising=False)
    with patch.object(data_source, "sheet_id", return_value=None):
        assert data_source.uses_google_sheets() is False


def test_uses_sheets_when_env_set(monkeypatch):
    monkeypatch.setenv("CHURCH_DATA_SOURCE", "sheets")
    monkeypatch.setenv("CHURCH_SHEET_ID", "abc123")
    assert data_source.uses_google_sheets() is True


def test_forces_csv_when_env_set(monkeypatch):
    monkeypatch.setenv("CHURCH_DATA_SOURCE", "csv")
    monkeypatch.setenv("CHURCH_SHEET_ID", "abc123")
    assert data_source.uses_google_sheets() is False


def test_load_service_account_json_skips_non_service_account(tmp_path):
    adc_file = tmp_path / "application_default_credentials.json"
    adc_file.write_text('{"type": "authorized_user", "client_id": "x"}', encoding="utf-8")
    assert data_source._load_service_account_json(adc_file) is None


def test_load_service_account_json_reads_service_account(tmp_path):
    sa_file = tmp_path / "sa.json"
    sa_file.write_text(
        '{"type": "service_account", "client_email": "sa@proj.iam.gserviceaccount.com"}',
        encoding="utf-8",
    )
    info = data_source._load_service_account_json(sa_file)
    assert info is not None
    assert info["client_email"] == "sa@proj.iam.gserviceaccount.com"


def test_get_gspread_client_raises_without_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    mock_gspread = MagicMock()
    monkeypatch.setitem(sys.modules, "gspread", mock_gspread)
    with patch.object(data_source, "_service_account_info", return_value=None):
        with pytest.raises(FileNotFoundError, match="no service account credentials"):
            data_source._get_gspread_client()


def test_get_gspread_client_uses_service_account(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    sa_info = {"type": "service_account", "client_email": "sa@proj.iam.gserviceaccount.com"}
    mock_client = MagicMock()
    mock_gspread = MagicMock()
    mock_gspread.service_account_from_dict.return_value = mock_client
    monkeypatch.setitem(sys.modules, "gspread", mock_gspread)
    with patch.object(data_source, "_service_account_info", return_value=sa_info):
        assert data_source._get_gspread_client() is mock_client
        mock_gspread.service_account_from_dict.assert_called_once()
