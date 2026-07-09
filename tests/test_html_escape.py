"""Tests for HTML escaping in calendar rendering."""

from __future__ import annotations

from views.shared import church_badge_html, format_event_day_html, render_calendar_grid_html


def test_church_badge_escapes_html():
    html_out = church_badge_html('<script>alert(1)</script>')
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_format_event_day_html_escapes_names():
    events = [{
        "type": "birthday",
        "name": "<img onerror=alert(1)>",
        "display_name": "<img onerror=alert(1)>",
        "church": "Filam",
    }]
    html_out = format_event_day_html(events)
    assert "<img" not in html_out
    assert "&lt;img" in html_out


def test_calendar_grid_renders_aria_label():
    html_out = render_calendar_grid_html(2026, 7, {}, __import__("datetime").date(2026, 7, 9))
    assert 'aria-label="July 2026 calendar"' in html_out
    assert 'scope="col"' in html_out
