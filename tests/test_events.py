"""Tests for calendar event building."""

from __future__ import annotations

import pandas as pd

from helpers import (
    build_admin_events,
    build_events,
    group_households,
    sanitize_events_for_public,
)


def _row(**overrides):
    base = {
        "Church_Affiliation": "Filam",
        "First_Name": "Alex",
        "Last_Name": "Sample",
        "Full_Name": "Alex Sample",
        "Birthday": "01/15",
        "Birthday_Month": 1,
        "Birthday_Day": 15,
        "Home_Address": "100 Demo St, Chicago, IL 60601",
        "Phone_Number": "",
        "Email_Address": "",
        "Wedding_Anniversary": "06/20",
        "Anniversary_Month": 6,
        "Anniversary_Day": 20,
        "Spouse_Name": "Jordan Sample",
        "Spouse_Birthday": "08/03",
        "Spouse_Phone": "",
        "Children_Names": "Sam",
        "Children_Birthdays": "04/10",
        "Is_Member": True,
        "Opt_In_Announcements": True,
        "City": "Chicago",
        "State": "IL",
    }
    base.update(overrides)
    return base


def test_anniversary_deduped_per_household():
    df = pd.DataFrame([
        _row(),
        _row(First_Name="Jordan", Last_Name="Sample", Full_Name="Jordan Sample", Birthday="08/03",
             Birthday_Month=8, Birthday_Day=3),
    ])
    events = build_events(df)
    anniversaries = [e for e in events if e["type"] == "anniversary"]
    assert len(anniversaries) == 1


def test_child_birthday_deduped_for_both_parents():
    df = pd.DataFrame([
        _row(),
        _row(First_Name="Jordan", Last_Name="Sample", Full_Name="Jordan Sample", Birthday="08/03",
             Birthday_Month=8, Birthday_Day=3),
    ])
    events = build_admin_events(df)
    child_events = [e for e in events if e["type"] == "child_birthday"]
    assert len(child_events) == 1
    assert "Sam" in child_events[0]["name"]


def test_group_households():
    df = pd.DataFrame([
        _row(),
        _row(First_Name="Jordan", Last_Name="Sample", Full_Name="Jordan Sample", Birthday="08/03",
             Birthday_Month=8, Birthday_Day=3),
    ])
    households = group_households(df)
    assert len(households) == 1
    assert households[0]["size"] == 2


def _hannah_promotion_df() -> pd.DataFrame:
    return pd.DataFrame([
        _row(
            First_Name="Parent",
            Last_Name="One",
            Full_Name="Parent One",
            Birthday="01/01",
            Birthday_Month=1,
            Birthday_Day=1,
            Children_Names="Hannah",
            Children_Birthdays="05/10",
        ),
        _row(
            First_Name="Hannah",
            Last_Name="Gonzalez",
            Full_Name="Hannah Gonzalez",
            Birthday="08/22",
            Birthday_Month=8,
            Birthday_Day=22,
            Home_Address="200 Other St, Naperville, IL 60540",
            Children_Names="",
            Children_Birthdays="",
            Wedding_Anniversary="",
            Anniversary_Month=None,
            Anniversary_Day=None,
            Spouse_Name="",
            Spouse_Birthday="",
        ),
    ])


def test_child_with_own_entry_suppresses_child_birthday():
    df = _hannah_promotion_df()
    events = build_admin_events(df)
    child_events = [e for e in events if e["type"] == "child_birthday"]
    hannah_birthdays = [
        e for e in events
        if e["type"] == "birthday" and "Hannah" in e["name"]
    ]
    assert child_events == []
    assert len(hannah_birthdays) == 1
    assert hannah_birthdays[0]["month"] == 8
    assert hannah_birthdays[0]["day"] == 22


def test_child_with_own_entry_appears_on_public_calendar():
    df = _hannah_promotion_df()
    public = sanitize_events_for_public(build_events(df))
    hannah_events = [e for e in public if e["name"] == "Hannah"]
    assert len(hannah_events) == 1
    assert hannah_events[0] == {
        "type": "birthday",
        "name": "Hannah",
        "month": 8,
        "day": 22,
        "church": "Filam",
    }


def test_child_name_variant_matches_own_directory_entry():
    df = pd.DataFrame([
        _row(
            First_Name="Parent",
            Last_Name="One",
            Full_Name="Parent One",
            Children_Names="Hannah Marie",
            Children_Birthdays="05/10",
        ),
        _row(
            First_Name="Hannah",
            Last_Name="Gonzalez",
            Full_Name="Hannah Gonzalez",
            Birthday="08/22",
            Birthday_Month=8,
            Birthday_Day=22,
            Home_Address="200 Other St, Naperville, IL 60540",
            Children_Names="",
            Children_Birthdays="",
        ),
    ])
    events = build_admin_events(df)
    assert not any(e["type"] == "child_birthday" for e in events)
