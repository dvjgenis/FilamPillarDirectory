"""Smoke tests for UI copy and shared navigation helpers."""

from auth import ADMIN_PAGE_LABELS
from helpers import CHURCH_COLORS, is_valid_coordinate, MAP_MAX_ZOOM, MAP_MIN_ZOOM
from views.shared import (
    CHART_HOVER_TEMPLATES,
    NAV_PENDING_KEY,
    apply_hover_sentences,
    build_regional_deck_view,
    calendar_legend_html,
)


def test_directory_is_first_admin_page():
    assert ADMIN_PAGE_LABELS[0] == "👥 Directory"


def test_chart_hover_templates_cover_key_charts():
    expected = {
        "church_pie",
        "city_bar",
        "city_bar_stacked",
        "month_stacked",
        "membership_grouped",
        "optin_stacked",
        "household_size",
    }
    assert expected.issubset(CHART_HOVER_TEMPLATES.keys())


def test_hover_templates_are_sentences():
    for key, template in CHART_HOVER_TEMPLATES.items():
        assert "<extra></extra>" in template, key
        assert len(template) > 20, key


def test_apply_hover_sentences_plotly():
    import plotly.express as px

    fig = px.bar(x=["A"], y=[1])
    apply_hover_sentences(fig, "city_bar")
    assert fig.data[0].hovertemplate == CHART_HOVER_TEMPLATES["city_bar"]


def test_calendar_legend_is_plain_language():
    legend = calendar_legend_html()
    assert "Birthday" in legend
    assert "Anniversary" in legend
    assert "Missionary" in legend
    assert CHURCH_COLORS["Missionary"] in legend
    assert "name" not in legend


def test_nav_pending_key_for_staff():
    assert NAV_PENDING_KEY == "nav_staff_pending"


def test_church_badge_uses_missionary_purple():
    from views.shared import church_badge_html

    badge = church_badge_html("Missionary")
    assert CHURCH_COLORS["Missionary"] in badge
    assert "Missionary" in badge


def test_valid_coordinates_accept_global_locations():
    assert is_valid_coordinate(41.9, -87.7) is True
    assert is_valid_coordinate(9.31, 123.31) is True


def test_build_regional_deck_view_allows_unrestricted_zoom():
    view_state, map_views = build_regional_deck_view(
        {"latitude": 41.8, "longitude": -87.6, "zoom": 3.0},
        max_zoom=20.0,
    )
    assert view_state.zoom == 3.0
    assert view_state.min_zoom == MAP_MIN_ZOOM
    assert view_state.max_zoom == 20.0
    controller = map_views[0].controller
    assert controller["minZoom"] == MAP_MIN_ZOOM
    assert controller["maxZoom"] == 20.0
    assert controller["keyboard"] is False
    assert controller["dragRotate"] is False
