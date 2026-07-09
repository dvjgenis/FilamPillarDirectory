"""Tests for calendar event building."""

from __future__ import annotations

import pandas as pd

from helpers import build_admin_events, build_events, group_households


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
