"""Shared UI helpers for public and admin views."""

from __future__ import annotations

import html
from datetime import date

import streamlit as st

from helpers import CHURCH_COLORS, MONTH_NAMES, church_full_name, event_icon, month_calendar_grid, style_figure

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
    font-size: 0.8rem;
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
    .cal-day { min-height: 72px; font-size: 0.75rem; }
}
</style>
"""

PUBLIC_WELCOME = (
    "Welcome to the Filam & Pillar community directory — "
    "a shared space to celebrate and connect with our church family."
)

MINOR_PRIVACY_NOTE = (
    "Children's names and birthdays on a parent's record are not shown here. "
    "Adults with their own directory entry may still appear in public views."
)


def apply_global_styles():
    st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)


def render_page_header(title: str, intro: str, *, show_minor_note: bool = False) -> None:
    """Title plus a short how-to-read-this-page caption."""
    st.title(title)
    st.caption(intro)
    if show_minor_note:
        render_minor_privacy_note()


def render_minor_privacy_note() -> None:
    """Subtle note about children's data exclusion on public views."""
    st.markdown(
        f'<p class="note-muted">ℹ️ {MINOR_PRIVACY_NOTE}</p>',
        unsafe_allow_html=True,
    )


def render_public_sidebar_welcome() -> None:
    st.caption(PUBLIC_WELCOME)


def render_staff_sidebar_welcome() -> None:
    st.caption(
        "Staff directory — full records for authorized use. "
        "Please handle all contact and family information with care."
    )


def show_chart(fig, **style_kwargs):
    style_figure(fig, **style_kwargs)
    st.plotly_chart(fig, width="stretch")


def church_badge_html(church: str) -> str:
    safe_church = html.escape(str(church or ""))
    color = CHURCH_COLORS.get(church, "#6B7280")
    return f'<span class="church-badge" style="background:{color}">{safe_church}</span>'


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


def render_calendar_controls(today: date) -> tuple[int, int]:
    """Shared month/year navigation controls. Returns (month, year)."""
    if "cal_month" not in st.session_state:
        st.session_state.cal_month = today.month
    if "cal_year" not in st.session_state:
        st.session_state.cal_year = today.year

    c_prev, c_month, c_year, c_next = st.columns([1, 2, 1, 1])
    with c_prev:
        if st.button("◀ Prev", key="cal_prev"):
            if st.session_state.cal_month == 1:
                st.session_state.cal_month = 12
                st.session_state.cal_year -= 1
            else:
                st.session_state.cal_month -= 1
            st.rerun()
    with c_month:
        month_idx = st.selectbox(
            "Month",
            range(1, 13),
            index=st.session_state.cal_month - 1,
            format_func=lambda m: MONTH_NAMES[m - 1],
            label_visibility="collapsed",
        )
        st.session_state.cal_month = month_idx
    with c_year:
        center = st.session_state.cal_year
        year_options = list(range(center - 1, center + 2))
        year_idx = st.selectbox(
            "Year",
            year_options,
            index=year_options.index(st.session_state.cal_year),
            label_visibility="collapsed",
        )
        st.session_state.cal_year = year_idx
    with c_next:
        if st.button("Next ▶", key="cal_next"):
            if st.session_state.cal_month == 12:
                st.session_state.cal_month = 1
                st.session_state.cal_year += 1
            else:
                st.session_state.cal_month += 1
            st.rerun()

    return st.session_state.cal_month, st.session_state.cal_year
