"""Tests for age-group derivation and directory filtering."""

from __future__ import annotations

from datetime import date

import pandas as pd

from helpers import (
    AGE_GROUP_ADULT,
    AGE_GROUP_BELOW_13,
    AGE_GROUP_SENIOR,
    AGE_GROUP_TEEN,
    _parse_mmdd,
    age_group_from_age,
    clean_directory,
    extra_age_source_columns,
    filter_people,
    normalize_age_group,
    resolve_person_age,
)


def _base_row(**overrides) -> dict:
    row = {
        "Church_Affiliation": "Filam",
        "First_Name": "Alex",
        "Last_Name": "Sample",
        "Birthday": "01/15",
        "Home_Address": "100 Demo St, Chicago, IL 60601",
        "Phone_Number": "3125550101",
        "Email_Address": "alex@example.com",
        "Wedding_Anniversary": "06/20",
        "Spouse_Name": "",
        "Spouse_Birthday": "",
        "Spouse_Phone": "",
        "Children_Names": "",
        "Children_Birthdays": "",
        "Is_Member": True,
        "Opt_In_Announcements": True,
    }
    row.update(overrides)
    return row


def test_age_group_from_age_buckets():
    assert age_group_from_age(0) == AGE_GROUP_BELOW_13
    assert age_group_from_age(12) == AGE_GROUP_BELOW_13
    assert age_group_from_age(13) == AGE_GROUP_TEEN
    assert age_group_from_age(18) == AGE_GROUP_TEEN
    assert age_group_from_age(19) == AGE_GROUP_ADULT
    assert age_group_from_age(64) == AGE_GROUP_ADULT
    assert age_group_from_age(65) == AGE_GROUP_SENIOR
    assert age_group_from_age(90) == AGE_GROUP_SENIOR


def test_normalize_age_group_aliases():
    assert normalize_age_group("under 13") == AGE_GROUP_BELOW_13
    assert normalize_age_group("youth") == AGE_GROUP_TEEN
    assert normalize_age_group("adult") == AGE_GROUP_ADULT
    assert normalize_age_group("seniors") == AGE_GROUP_SENIOR
    assert normalize_age_group("") == ""
    assert normalize_age_group("unknown") == ""


def test_parse_mmdd_accepts_year():
    assert _parse_mmdd("01/15") == (1, 15)
    assert _parse_mmdd("01/15/1990") == (1, 15)
    assert _parse_mmdd("1990-01-15") == (1, 15)


def test_resolve_person_age_prefers_explicit_age():
    today = date(2026, 9, 4)
    row = {"Age": "16", "Birth_Year": 2000, "Birthday": "01/15/2010"}
    assert resolve_person_age(row, today=today) == 16


def test_resolve_person_age_from_birthday_year():
    today = date(2026, 9, 4)
    row = {"Age": "", "Birthday": "01/15/2010", "Birthday_Month": 1, "Birthday_Day": 15}
    assert resolve_person_age(row, today=today) == 16


def test_resolve_person_age_from_birth_year():
    today = date(2026, 9, 4)
    row = {"Birth_Year": 1950, "Birthday": "03/25", "Birthday_Month": 3, "Birthday_Day": 25}
    assert resolve_person_age(row, today=today) == 76


def test_clean_directory_derives_age_group_from_age():
    df = clean_directory(pd.DataFrame([
        _base_row(First_Name="Kid", Last_Name="One", Age=10),
        _base_row(First_Name="Teen", Last_Name="Two", Age=15),
        _base_row(First_Name="Adult", Last_Name="Three", Age=40),
        _base_row(First_Name="Senior", Last_Name="Four", Age=70),
    ]))
    assert df["Age_Group"].tolist() == [
        AGE_GROUP_BELOW_13,
        AGE_GROUP_TEEN,
        AGE_GROUP_ADULT,
        AGE_GROUP_SENIOR,
    ]


def test_clean_directory_uses_age_group_label_without_age():
    df = clean_directory(pd.DataFrame([
        _base_row(First_Name="Pat", Last_Name="Label", Age="", Age_Group="seniors"),
    ]))
    assert df.iloc[0]["Age_Group"] == AGE_GROUP_SENIOR
    assert pd.isna(df.iloc[0]["Age"])


def test_clean_directory_without_age_columns():
    df = clean_directory(pd.DataFrame([_base_row()]))
    assert "Age_Group" in df.columns
    assert df.iloc[0]["Age_Group"] == ""
    assert pd.isna(df.iloc[0]["Age"])


def test_filter_people_age_groups():
    df = clean_directory(pd.DataFrame([
        _base_row(First_Name="Kid", Last_Name="A", Age=10),
        _base_row(First_Name="Teen", Last_Name="B", Age=16),
        _base_row(First_Name="Adult", Last_Name="C", Age=40),
        _base_row(First_Name="Senior", Last_Name="D", Age=71),
        _base_row(First_Name="Eighteen", Last_Name="E", Age=18),
    ]))

    kids = filter_people(df, age_group_filter=AGE_GROUP_BELOW_13)
    assert set(kids["First_Name"]) == {"Kid"}

    teens = filter_people(df, age_group_filter=AGE_GROUP_TEEN)
    assert set(teens["First_Name"]) == {"Teen", "Eighteen"}

    adults = filter_people(df, age_group_filter=AGE_GROUP_ADULT)
    assert set(adults["First_Name"]) == {"Adult", "Senior", "Eighteen"}

    seniors = filter_people(df, age_group_filter=AGE_GROUP_SENIOR)
    assert set(seniors["First_Name"]) == {"Senior"}


def test_filter_people_age_group_from_label_includes_seniors_in_18_plus():
    df = clean_directory(pd.DataFrame([
        _base_row(First_Name="Adult", Last_Name="A", Age_Group="18+"),
        _base_row(First_Name="Senior", Last_Name="B", Age_Group="Seniors 65+"),
        _base_row(First_Name="Kid", Last_Name="C", Age_Group="Below 13"),
    ]))
    adults = filter_people(df, age_group_filter=AGE_GROUP_ADULT)
    assert set(adults["First_Name"]) == {"Adult", "Senior"}


def test_extra_age_source_columns_aliases():
    assert extra_age_source_columns(["Church_Affiliation", "Age Group", "birth year"]) == [
        "Age Group",
        "birth year",
    ]
