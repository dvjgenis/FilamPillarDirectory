"""Smoke tests for UI copy and shared navigation helpers."""

from auth import PUBLIC_PAGE_LABELS, PUBLIC_PAGES
from helpers import is_map_display_coordinate
from views.shared import (
    CHART_HOVER_TEMPLATES,
    PUBLIC_WELCOME_SHORT,
    apply_hover_sentences,
    build_regional_deck_view,
    calendar_legend_html,
)


def test_home_is_first_public_page():
    assert PUBLIC_PAGES[0][1] == "🏠 Home"
    assert PUBLIC_PAGE_LABELS[0] == "🏠 Home"


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
    assert "name" not in legend


def test_public_welcome_is_short():
    assert len(PUBLIC_WELCOME_SHORT) < len(
        "Welcome to the Filam & Pillar community directory — "
        "a shared space to celebrate and connect with our church family."
    )


def test_queue_navigation_uses_pending_key():
    from views.shared import NAV_PENDING_KEY, queue_navigation

    class FakeState(dict):
        def pop(self, key, default=None):
            return super().pop(key, default)

    state = FakeState()
    # queue_navigation writes to session state; verify key name contract
    assert NAV_PENDING_KEY == "nav_public_pending"


def test_apply_pending_navigation_key_mapping():
    from views.shared import NAV_PENDING_KEY

    assert NAV_PENDING_KEY == "nav_public_pending"


def test_map_bounds_still_exclude_philippines():
    assert is_map_display_coordinate(41.9, -87.7) is True
    assert is_map_display_coordinate(9.31, 123.31) is False


def test_build_regional_deck_view_enforces_zoom_limits():
    view_state, map_views = build_regional_deck_view(
        {"latitude": 41.8, "longitude": -87.6, "zoom": 3.0},
        max_zoom=11.0,
    )
    assert view_state.zoom == 7.0
    assert view_state.min_zoom == 7.0
    assert view_state.max_zoom == 11.0
    assert map_views[0].controller["minZoom"] == 7.0
    assert map_views[0].controller["maxZoom"] == 11.0
