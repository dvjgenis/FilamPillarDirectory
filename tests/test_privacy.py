"""Tests for public privacy guarantees."""

from __future__ import annotations

import pandas as pd
import pytest

from helpers import (
    SENSITIVE_FIELDS,
    assert_public_safe_columns,
    build_admin_events,
    build_events,
    get_public_aggregate_df,
    get_public_df,
    sanitize_events_for_public,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Church_Affiliation": "Filam",
            "First_Name": "Alex",
            "Last_Name": "Sample",
            "Full_Name": "Alex Sample",
            "Birthday": "01/15",
            "Birthday_Month": 1,
            "Birthday_Day": 15,
            "Home_Address": "100 Demo St, Chicago, IL 60601",
            "Phone_Number": "3125550101",
            "Email_Address": "alex@example.com",
            "Wedding_Anniversary": "06/20",
            "Anniversary_Month": 6,
            "Anniversary_Day": 20,
            "Spouse_Name": "Jordan",
            "Spouse_Birthday": "08/03",
            "Spouse_Phone": "3125550102",
            "Children_Names": "Sam",
            "Children_Birthdays": "04/10",
            "Is_Member": True,
            "Opt_In_Announcements": True,
            "City": "Chicago",
            "State": "IL",
        }
    ])


def test_get_public_df_excludes_sensitive_fields():
    df = _sample_df()
    public = get_public_df(df)
    assert set(public.columns) == {"First_Name", "Last_Name", "Full_Name", "Church_Affiliation"}
    for field in SENSITIVE_FIELDS:
        assert field not in public.columns


def test_get_public_aggregate_df_allows_city_only():
    df = _sample_df()
    aggregate = get_public_aggregate_df(df)
    assert "City" in aggregate.columns
    assert "Phone_Number" not in aggregate.columns


def test_assert_public_safe_columns_raises():
    df = _sample_df()
    with pytest.raises(ValueError, match="sensitive columns"):
        assert_public_safe_columns(df)


def test_sanitize_events_for_public_first_names_only():
    events = [
        {"type": "birthday", "name": "Alex Sample", "first_name": "Alex", "month": 1, "day": 15, "church": "Filam"},
        {"type": "anniversary", "name": "Alex Sample & Jordan Sample", "first_name": None, "month": 6, "day": 20, "church": "Filam"},
    ]
    public = sanitize_events_for_public(events)
    assert public[0]["name"] == "Alex"
    assert public[1]["name"] == "Alex & Jordan"


def test_public_events_exclude_children_from_parent_records():
    df = pd.DataFrame([
        {
            "Church_Affiliation": "Filam",
            "First_Name": "Parent",
            "Last_Name": "One",
            "Full_Name": "Parent One",
            "Birthday": "01/01",
            "Birthday_Month": 1,
            "Birthday_Day": 1,
            "Home_Address": "100 Demo St, Chicago, IL 60601",
            "Phone_Number": "",
            "Email_Address": "",
            "Wedding_Anniversary": "",
            "Anniversary_Month": None,
            "Anniversary_Day": None,
            "Spouse_Name": "",
            "Spouse_Birthday": "",
            "Spouse_Phone": "",
            "Children_Names": "Child One",
            "Children_Birthdays": "05/05",
            "Is_Member": True,
            "Opt_In_Announcements": True,
            "City": "Chicago",
            "State": "IL",
        }
    ])
    public_events = build_events(df)
    admin_events = build_admin_events(df)
    assert all(e["type"] != "child_birthday" for e in public_events)
    assert any(e["type"] == "child_birthday" for e in admin_events)
