"""Tests for CSV loading and cleaning."""

from __future__ import annotations

import pandas as pd
import pytest

from helpers import CSV_COLUMNS, load_and_clean


@pytest.fixture
def sample_csv(tmp_path, monkeypatch):
    csv_path = tmp_path / "sample.csv"
    rows = [
        {
            "Church_Affiliation": "Filam",
            "First_Name": "Alex",
            "Last_Name": "Sample",
            "Birthday": "01/15",
            "Home_Address": "100 Demo St, Chicago, IL 60601",
            "Phone_Number": "3125550101",
            "Email_Address": "alex@example.com",
            "Wedding_Anniversary": "06/20",
            "Spouse_Name": "Jordan Sample",
            "Spouse_Birthday": "08/03",
            "Spouse_Phone": "3125550102",
            "Children_Names": "Sam",
            "Children_Birthdays": "04/10",
            "Is_Member": True,
            "Opt_In_Announcements": True,
        },
        {
            "Church_Affiliation": "Pillar",
            "First_Name": "",
            "Last_Name": "",
            "Birthday": "",
            "Home_Address": "",
            "Phone_Number": "",
            "Email_Address": "",
            "Wedding_Anniversary": "",
            "Spouse_Name": "",
            "Spouse_Birthday": "",
            "Spouse_Phone": "",
            "Children_Names": "",
            "Children_Birthdays": "",
            "Is_Member": False,
            "Opt_In_Announcements": False,
        },
    ]
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    monkeypatch.setenv("CHURCH_CSV_PATH", str(csv_path))
    monkeypatch.setattr("helpers.CSV_PATH", csv_path)
    return csv_path


def test_load_and_clean_filters_blank_rows(sample_csv):
    df = load_and_clean()
    assert len(df) == 1
    assert df.iloc[0]["Full_Name"] == "Alex Sample"
    assert bool(df.iloc[0]["Is_Member"]) is True
    assert df.iloc[0]["Birthday_Month"] == 1
    assert df.iloc[0]["Birthday_Day"] == 15
    assert df.iloc[0]["City"] == "Chicago"


def test_load_and_clean_missing_columns(tmp_path, monkeypatch):
    csv_path = tmp_path / "bad.csv"
    pd.DataFrame({"First_Name": ["A"]}).to_csv(csv_path, index=False)
    monkeypatch.setattr("helpers.CSV_PATH", csv_path)
    with pytest.raises(ValueError, match="missing expected columns"):
        load_and_clean()


def test_csv_columns_contract():
    assert len(CSV_COLUMNS) == 15
