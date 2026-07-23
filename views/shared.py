"""Shared UI helpers for public and admin views."""

from __future__ import annotations

import html
from collections.abc import Callable
from datetime import date
from typing import Any

import streamlit as st

import pydeck as pdk

from helpers import (
    CHURCH_COLORS,
    MONTH_NAMES,
    MAP_MAX_ZOOM,
    MAP_MIN_ZOOM,
    church_full_name,
    church_color_legend_html,
    event_icon,
    month_calendar_grid,
    style_figure,
)

GLOBAL_STYLES = """
<style>
.church-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    color: white;
    margin-bottom: 4px;
}
.light-surface {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 12px;
    color: #1F2937;
}
.hero-card {
    background: linear-gradient(135deg, #EFF6FF 0%, #F8FAFC 55%, #FFFFFF 100%);
    border: 1px solid #BFDBFE;
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 1.5rem;
}
.hero-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1E3A8A;
    margin: 0 0 8px 0;
    line-height: 1.3;
}
.hero-subtitle {
    font-size: 1rem;
    color: #475569;
    margin: 0;
    line-height: 1.5;
}
.quick-link-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 16px 18px;
    height: 100%;
    transition: border-color 0.15s;
}
.quick-link-card:hover {
    border-color: #93C5FD;
}
.quick-link-title {
    font-size: 1rem;
    font-weight: 600;
    color: #1F2937;
    margin: 0 0 6px 0;
}
.quick-link-desc {
    font-size: 0.85rem;
    color: #64748B;
    margin: 0;
    line-height: 1.4;
}
.viz-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 16px 18px 8px 18px;
    margin-bottom: 1rem;
}
.viz-question {
    font-size: 1.1rem;
    font-weight: 600;
    color: #1F2937;
    margin: 0 0 4px 0;
}
.viz-caption {
    font-size: 0.85rem;
    color: #64748B;
    margin: 0 0 12px 0;
    line-height: 1.4;
}
.info-callout {
    background: #F0F9FF;
    border: 1px solid #BAE6FD;
    border-radius: 10px;
    padding: 12px 16px;
    color: #0C4A6E;
    font-size: 0.9rem;
    line-height: 1.5;
    margin-bottom: 1rem;
}
.info-callout-warn {
    background: #FFFBEB;
    border-color: #FDE68A;
    color: #92400E;
}
.lookup-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
}
.lookup-table th {
    text-align: left;
    padding: 10px 12px;
    background: #F8FAFC;
    border-bottom: 2px solid #E5E7EB;
    color: #374151;
    font-weight: 600;
}
.lookup-table td {
    padding: 10px 12px;
    border-bottom: 1px solid #F1F5F9;
    color: #1F2937;
}
.lookup-table tr:hover td {
    background: #F8FAFC;
}
.calendar-scroll-wrap {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}
.cal-grid {
    width: 100%;
    border-collapse: separate;
    border-spacing: 6px;
    table-layout: fixed;
}
.cal-grid th {
    color: #374151;
    font-weight: 700;
    font-size: 0.85rem;
    text-align: center;
    padding-bottom: 4px;
}
.cal-grid td {
    vertical-align: top;
}
.cal-day {
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 8px;
    min-height: 90px;
    font-size: 0.82rem;
    background: #FFFFFF;
}
.cal-day-today {
    border: 2px solid #2563EB;
    background: #EFF6FF;
}
.cal-day-header {
    font-weight: 700;
    font-size: 0.9rem;
    margin-bottom: 4px;
    color: #374151;
}
.cal-event-bday { color: #2563EB; }
.cal-event-anniv { color: #DC2626; }
.metric-sub { font-size: 0.8rem; color: #94A3B8; }
.note-muted { font-size: 0.8rem; color: #64748B; line-height: 1.4; }
@media (max-width: 768px) {
    .cal-grid { min-width: 640px; }
    .cal-day { min-height: 72px; font-size: 0.78rem; }
    .hero-card { padding: 20px; }
}
</style>
"""

CHART_HOVER_TEMPLATES = {
    "church_pie": (
        "<b>%{label}</b> makes up %{percent} of the community "
        "(%{value} people).<extra></extra>"
    ),
    "city_bar": "<b>%{y}</b> has %{x} people in the directory.<extra></extra>",
    "city_bar_stacked": (
        "<b>%{y}</b> has %{x} people from %{fullData.name}.<extra></extra>"
    ),
    "month_stacked": (
        "<b>%{x}</b>: %{y} %{fullData.name} celebrations.<extra></extra>"
    ),
    "membership_grouped": (
        "<b>%{x}</b> — %{y} people are %{fullData.name}.<extra></extra>"
    ),
    "optin_stacked": (
        "<b>%{x}</b> — %{y} people are %{fullData.name}.<extra></extra>"
    ),
    "household_size": (
        "<b>%{x}</b> people per household: %{y} households.<extra></extra>"
    ),
    "event_timeline": (
        "<b>%{hovertext}</b> on day %{x} (%{fullData.name}).<extra></extra>"
    ),
}

MINOR_PRIVACY_NOTE = (
    "Children's names and birthdays on a parent's record are not shown here. "
    "Adults with their own directory entry may still appear in public views."
)

PUBLIC_PRIVACY_NOTE = (
    "Public pages show limited information only — names, churches, and grouped statistics. "
    "No phone numbers, emails, or home addresses appear here."
)

NAV_PENDING_KEY = "nav_staff_pending"


def apply_pending_navigation(nav_key: str = "nav_staff") -> None:
    """Apply a pending sidebar page change before the nav radio widget renders."""
    pending_key = f"{nav_key}_pending"
    pending = st.session_state.pop(pending_key, None)
    if pending is not None:
        st.session_state[nav_key] = pending


def queue_navigation(page_label: str, nav_key: str = "nav_staff") -> None:
    """Queue a sidebar navigation change for the next run (before widgets render)."""
    pending_key = f"{nav_key}_pending"
    st.session_state[pending_key] = page_label


def build_regional_deck_view(
    view_state: dict[str, float],
    *,
    max_zoom: float = MAP_MAX_ZOOM,
) -> tuple[pdk.ViewState, list[pdk.View]]:
    """Return ViewState + MapView controller with unrestricted zoom."""
    zoom = view_state["zoom"]
    initial_view_state = pdk.ViewState(
        latitude=view_state["latitude"],
        longitude=view_state["longitude"],
        zoom=zoom,
        min_zoom=MAP_MIN_ZOOM,
        max_zoom=max_zoom,
        pitch=0,
    )
    views = [
        pdk.View(
            type="MapView",
            controller={
                "minZoom": MAP_MIN_ZOOM,
                "maxZoom": max_zoom,
                "scrollZoom": True,
                "doubleClickZoom": True,
                "touchZoom": True,
                "dragPan": True,
                "dragRotate": False,
                "touchRotate": False,
                "keyboard": False,
            },
        )
    ]
    return initial_view_state, views


def apply_global_styles():
    st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)


def render_page_header(
    title: str,
    intro: str,
    *,
    question: str | None = None,
    show_minor_note: bool = False,
) -> None:
    """Title plus a short how-to-read-this-page caption."""
    st.title(title)
    if question:
        st.markdown(f'<p class="viz-question">{html.escape(question)}</p>', unsafe_allow_html=True)
    st.caption(intro)
    if show_minor_note:
        render_minor_privacy_note()


def render_minor_privacy_note() -> None:
    """Subtle note about children's data exclusion on public views."""
    st.markdown(
        f'<p class="note-muted">ℹ️ {MINOR_PRIVACY_NOTE}</p>',
        unsafe_allow_html=True,
    )


def render_staff_sidebar_welcome() -> None:
    st.caption(
        "Staff directory — full contact and family records. "
        "Please handle all information with care."
    )


def render_info_callout(text: str, *, icon: str = "ℹ️", variant: str = "info") -> None:
    """Friendly highlighted callout box."""
    cls = "info-callout" if variant == "info" else "info-callout info-callout-warn"
    st.markdown(
        f'<div class="{cls}">{icon} {html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_metric_row(metrics: list[tuple[str, Any, str | None]]) -> None:
    """Render a row of metrics with optional help tooltips.

    Each item is (label, value, help_text_or_none).
    """
    cols = st.columns(len(metrics))
    for col, (label, value, help_text) in zip(cols, metrics):
        with col:
            if help_text:
                st.metric(label, value, help=help_text)
            else:
                st.metric(label, value)


def render_viz_card(
    question: str,
    caption: str,
    render_content: Callable[[], None],
) -> None:
    """Wrap a visualization with a guiding question and how-to-read caption."""
    st.markdown(
        f'<div class="viz-card">'
        f'<p class="viz-question">{html.escape(question)}</p>'
        f'<p class="viz-caption">{html.escape(caption)}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )
    render_content()


def apply_hover_sentences(fig, template_key: str) -> None:
    """Apply a sentence-style Plotly hover template to all traces."""
    template = CHART_HOVER_TEMPLATES.get(template_key)
    if template:
        fig.update_traces(hovertemplate=template)


def show_chart(fig, **style_kwargs):
    if "theme" not in style_kwargs:
        style_kwargs["theme"] = "light"
    style_figure(fig, **style_kwargs)
    st.plotly_chart(fig, width="stretch")


def church_badge_html(church: str) -> str:
    safe_church = html.escape(str(church or ""))
    color = CHURCH_COLORS.get(church, "#6B7280")
    return f'<span class="church-badge" style="background:{color}">{safe_church}</span>'


def render_lookup_table(rows: list[dict]) -> None:
    """Render a styled HTML table with church badges for name lookup."""
    if not rows:
        return
    parts = [
        '<table class="lookup-table">',
        "<thead><tr><th>First Name</th><th>Last Name</th><th>Church</th></tr></thead>",
        "<tbody>",
    ]
    for row in rows:
        first = html.escape(str(row.get("First_Name", "")))
        last = html.escape(str(row.get("Last_Name", "")))
        church = row.get("Church_Affiliation", "")
        badge = church_badge_html(str(church))
        parts.append(f"<tr><td>{first}</td><td>{last}</td><td>{badge}</td></tr>")
    parts.append("</tbody></table>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def format_event_day_html(day_events: list, max_visible: int = 3) -> str:
    """Build calendar cell HTML with overflow handling."""
    event_html = ""
    for e in day_events[:max_visible]:
        icon = event_icon(e["type"])
        color = CHURCH_COLORS.get(e["church"], "#6B7280")
        label = e.get("display_name", e["name"])
        short_name = label.split(" ")[0]
        if e["type"] == "anniversary":
            parts = [p.strip() for p in e["name"].split(" & ") if p.strip()]
            short_name = " & ".join(p.split(" ")[0] for p in parts) if parts else e["name"]
        elif e["type"] == "child_birthday":
            short_name = e["name"].split(" ")[0]
        if not short_name.strip():
            short_name = e.get("name", "Event")
        safe_name = html.escape(short_name)
        event_html += f'<div style="color:{color}">{icon} {safe_name}</div>'

    overflow = len(day_events) - max_visible
    if overflow > 0:
        event_html += (
            f'<div style="color:#6B7280;font-size:0.75rem">+{overflow} more</div>'
        )
    return event_html


def render_calendar_grid_html(
    year: int,
    month: int,
    events_by_day: dict[int, list],
    today: date,
) -> str:
    """Render the full month grid as a single light-surface HTML table."""
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weeks = month_calendar_grid(year, month)
    month_name = html.escape(MONTH_NAMES[month - 1])

    html_parts = [
        '<div class="light-surface calendar-surface calendar-scroll-wrap">',
        f'<table class="cal-grid" aria-label="{month_name} {year} calendar">',
        "<thead><tr>",
    ]
    for day_name in weekdays:
        html_parts.append(f'<th scope="col">{day_name}</th>')
    html_parts.append("</tr></thead><tbody>")

    for week in weeks:
        html_parts.append("<tr>")
        for day_num in week:
            if day_num is None:
                html_parts.append('<td><div class="cal-day" style="background:#F9FAFB"></div></td>')
            else:
                is_today = (
                    month == today.month
                    and day_num == today.day
                    and year == today.year
                )
                cls = "cal-day cal-day-today" if is_today else "cal-day"
                day_events = events_by_day.get(day_num, [])
                event_html = format_event_day_html(day_events)
                html_parts.append(
                    f'<td><div class="{cls}">'
                    f'<div class="cal-day-header">{day_num}</div>'
                    f"{event_html}</div></td>"
                )
        html_parts.append("</tr>")

    html_parts.append("</tbody></table></div>")
    return "".join(html_parts)


def calendar_overflow_by_day(events_by_day: dict[int, list], max_visible: int = 3) -> dict[int, list]:
    """Return day -> hidden events for days with more than max_visible entries."""
    overflow: dict[int, list] = {}
    for day_num, day_events in events_by_day.items():
        if len(day_events) > max_visible:
            overflow[day_num] = day_events[max_visible:]
    return overflow


def render_calendar_overflow(days_with_overflow: dict[int, list]) -> None:
    """Show expandable list of calendar events hidden behind '+N more'."""
    if not days_with_overflow:
        return
    with st.expander("Additional events this month", expanded=False):
        for day_num in sorted(days_with_overflow):
            events = days_with_overflow[day_num]
            labels = []
            for e in events:
                icon = event_icon(e["type"])
                name = html.escape(e.get("display_name", e.get("name", "Event")))
                labels.append(f"{icon} {name}")
            st.markdown(f"**Day {day_num}:** " + " · ".join(labels), unsafe_allow_html=True)


def render_calendar_controls(today: date, *, mode: str = "public") -> tuple[int, int]:
    """Shared month/year navigation controls. Returns (month, year)."""
    month_key = f"cal_month_{mode}"
    year_key = f"cal_year_{mode}"
    prev_key = f"cal_prev_{mode}"
    next_key = f"cal_next_{mode}"

    if month_key not in st.session_state:
        st.session_state[month_key] = today.month
    if year_key not in st.session_state:
        st.session_state[year_key] = today.year

    c_prev, c_month, c_year, c_next = st.columns([1, 2, 1, 1])
    with c_prev:
        if st.button("◀ Prev", key=prev_key):
            if st.session_state[month_key] == 1:
                st.session_state[month_key] = 12
                st.session_state[year_key] -= 1
            else:
                st.session_state[month_key] -= 1
            st.rerun()
    with c_month:
        month_idx = st.selectbox(
            "Month",
            range(1, 13),
            index=st.session_state[month_key] - 1,
            format_func=lambda m: MONTH_NAMES[m - 1],
            label_visibility="collapsed",
            key=f"cal_month_select_{mode}",
        )
        st.session_state[month_key] = month_idx
    with c_year:
        center = st.session_state[year_key]
        year_options = list(range(center - 3, center + 4))
        year_idx = st.selectbox(
            "Year",
            year_options,
            index=year_options.index(st.session_state[year_key]),
            label_visibility="collapsed",
            key=f"cal_year_select_{mode}",
        )
        st.session_state[year_key] = year_idx
    with c_next:
        if st.button("Next ▶", key=next_key):
            if st.session_state[month_key] == 12:
                st.session_state[month_key] = 1
                st.session_state[year_key] += 1
            else:
                st.session_state[month_key] += 1
            st.rerun()

    return st.session_state[month_key], st.session_state[year_key]


def calendar_legend_html(*, include_children: bool = False) -> str:
    """Plain-language calendar color legend."""
    parts = [
        church_color_legend_html(separator=" &nbsp;&nbsp; "),
        "🎂 Birthday",
    ]
    if include_children:
        parts.append("👶 Child birthday")
    parts.append("💍 Anniversary")
    return " &nbsp;&nbsp; ".join(parts)
