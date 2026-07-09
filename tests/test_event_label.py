"""Tests for admin event label helper."""

import pandas as pd

from views.admin_views import _event_label


def test_event_label_falls_back_when_display_name_is_nan():
    row = pd.Series({"name": "Brad Blissett", "display_name": float("nan")})
    assert _event_label(row) == "Brad Blissett"


def test_event_label_uses_display_name_when_present():
    row = pd.Series({
        "name": "Sam",
        "display_name": "Sam (child of Pat & Chris)",
    })
    assert _event_label(row) == "Sam (child of Pat & Chris)"


def test_event_label_works_with_dict():
    event = {"name": "Ruel (Pastor) Akut"}
    assert _event_label(event) == "Ruel (Pastor) Akut"
