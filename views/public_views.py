"""Public-safe dashboard pages."""

from __future__ import annotations

import html
from datetime import date

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from helpers import (
    CHURCH_COLORS,
    MONTH_NAMES,
    build_church_map_data,
    build_public_density_data,
    church_full_name,
    city_church_breakdown,
    display_value,
    filter_people,
    get_events_for_month,
    get_public_df,
    get_today_events,
    get_upcoming_events,
    geocode_missing_count,
    month_event_counts_by_church,
)
from views.shared import (
    apply_hover_sentences,
    calendar_legend_html,
    calendar_overflow_by_day,
    PUBLIC_PRIVACY_NOTE,
    render_calendar_controls,
    render_calendar_grid_html,
    render_calendar_overflow,
    render_info_callout,
    render_lookup_table,
    render_metric_row,
    render_page_header,
    render_viz_card,
    render_welcome_hero,
    run_map_geocoding_if_needed,
    show_chart,
)


def page_home(df, events):
    today = date.today()
    month_events = get_events_for_month(events, today.month)
    upcoming_count = len(get_upcoming_events(events, today, 30))

    render_welcome_hero(
        title="Welcome to the Filam & Pillar Community",
        subtitle=(
            "A shared space to celebrate birthdays and anniversaries, explore where our "
            "church family lives, and find people across Fil-American and Pillar of Faith."
        ),
        stats=[
            ("People", len(df), "Total people listed in the community directory."),
            ("Churches", df["Church_Affiliation"].nunique(), "Filam and Pillar congregations."),
            (
                "Celebrations this month",
                len(month_events),
                f"Birthdays and anniversaries in {MONTH_NAMES[today.month - 1]}.",
            ),
        ],
        quick_links=[
            (
                "📊 Overview",
                "Community Overview",
                "How is our community spread across cities and churches?",
            ),
            (
                "📅 Celebrations",
                "Celebrations",
                "Whose birthday or anniversary is coming up?",
            ),
            (
                "🗺️ Map",
                "Community Map",
                "Where do we live as a community (privacy-safe)?",
            ),
            (
                "🔍 Name Lookup",
                "Name Lookup",
                "Which church is someone part of?",
            ),
        ],
    )

    if upcoming_count:
        render_info_callout(
            f"There are {upcoming_count} birthdays and anniversaries in the next 30 days. "
            "Visit Celebrations to see who's coming up.",
            icon="🎉",
        )

    render_info_callout(PUBLIC_PRIVACY_NOTE, icon="🔒")

    st.caption("Authorized staff can sign in via **Staff Login** in the sidebar for the full directory.")


def page_overview(df, events):
    render_page_header(
        "📊 Community Overview",
        "Community-wide totals and trends. Charts show grouped counts, not individual profiles.",
        question="What does our community look like at a glance?",
    )

    render_metric_row([
        ("People", len(df), "Everyone listed in the directory."),
        ("Churches", df["Church_Affiliation"].nunique(), "Filam and Pillar congregations."),
    ])

    c1, c2 = st.columns(2)

    with c1:
        def _church_pie():
            church_counts = df["Church_Affiliation"].value_counts().reset_index()
            church_counts.columns = ["Church", "Count"]
            fig = px.pie(
                church_counts,
                names="Church",
                values="Count",
                color="Church",
                color_discrete_map=CHURCH_COLORS,
                hole=0.45,
            )
            apply_hover_sentences(fig, "church_pie")
            show_chart(fig, pie=True, show_legend=True)

        render_viz_card(
            "How is the community split between Filam and Pillar?",
            "Each slice is one person; totals only, no names.",
            _church_pie,
        )

    with c2:
        def _city_bar():
            city_counts = df["City"].value_counts().head(10).reset_index()
            city_counts.columns = ["City", "People"]
            fig = px.bar(
                city_counts,
                x="People",
                y="City",
                orientation="h",
                color_discrete_sequence=["#6366F1"],
                text="People",
                labels={"People": "People", "City": "City"},
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(yaxis=dict(autorange="reversed"))
            apply_hover_sentences(fig, "city_bar")
            show_chart(fig, height=400)

        render_viz_card(
            "Which cities have the most people?",
            "Top 10 cities by headcount across both churches.",
            _city_bar,
        )

    hc1, hc2 = st.columns(2)

    with hc1:
        def _bday_chart():
            bday_counts = month_event_counts_by_church(events, "birthday")
            fig = px.bar(
                bday_counts,
                x="month_name",
                y="count",
                color="church",
                color_discrete_map=CHURCH_COLORS,
                barmode="stack",
                labels={"month_name": "Month", "count": "Celebrations", "church": "Church"},
            )
            apply_hover_sentences(fig, "month_stacked")
            show_chart(fig, height=300)

        render_viz_card(
            "When are birthdays spread through the year?",
            "Stacked bars show how many birthdays fall in each month, by church.",
            _bday_chart,
        )

    with hc2:
        def _anniv_chart():
            anniv_counts = month_event_counts_by_church(events, "anniversary")
            fig = px.bar(
                anniv_counts,
                x="month_name",
                y="count",
                color="church",
                color_discrete_map=CHURCH_COLORS,
                barmode="stack",
                labels={"month_name": "Month", "count": "Celebrations", "church": "Church"},
            )
            apply_hover_sentences(fig, "month_stacked")
            show_chart(fig, height=300)

        render_viz_card(
            "When are anniversaries spread through the year?",
            "Same pattern for wedding anniversaries, stacked by church.",
            _anniv_chart,
        )


def page_celebrations(events):
    render_page_header(
        "📅 Celebrations",
        "A month-by-month look at birthdays and anniversaries. Only first names are shown publicly.",
        question="Who are we celebrating?",
        show_minor_note=True,
    )

    today = date.today()

    with st.sidebar.expander("Calendar filters", expanded=True):
        event_filter = st.radio("Show", ["Both", "Birthdays", "Anniversaries"], key="pub_event_filter")
        st.divider()
        st.subheader("Upcoming 30 Days")
        upcoming = get_upcoming_events(events, today, 30)
        if event_filter == "Birthdays":
            upcoming = [e for e in upcoming if e["type"] == "birthday"]
        elif event_filter == "Anniversaries":
            upcoming = [e for e in upcoming if e["type"] == "anniversary"]

        if upcoming:
            for e in upcoming[:20]:
                icon = "🎂" if e["type"] == "birthday" else "💍"
                safe_name = html.escape(e["name"])
                st.markdown(
                    f"{icon} **{safe_name}**  \n"
                    f"<span class='metric-sub'>{MONTH_NAMES[e['month']-1]} {e['day']} "
                    f"({e['days_away']}d away)</span>",
                    unsafe_allow_html=True,
                )
            if len(upcoming) > 20:
                st.caption("See the full month in the calendar below.")
        else:
            st.caption("No upcoming events in the next 30 days.")

    today_events = get_today_events(events, today)
    if today_events:
        names = ", ".join(
            f"{'🎂' if e['type'] == 'birthday' else '💍'} {html.escape(e['name'])}" for e in today_events
        )
        st.success(f"**Today ({today.strftime('%B %d')}):** {names}")

    month_idx, year_idx = render_calendar_controls(today, mode="public")

    month_events = get_events_for_month(events, month_idx)
    if event_filter == "Birthdays":
        month_events = [e for e in month_events if e["type"] == "birthday"]
    elif event_filter == "Anniversaries":
        month_events = [e for e in month_events if e["type"] == "anniversary"]

    events_by_day: dict[int, list] = {}
    for e in month_events:
        events_by_day.setdefault(e["day"], []).append(e)

    st.markdown(
        '<p class="viz-question">Who are we celebrating this month?</p>',
        unsafe_allow_html=True,
    )
    st.caption(f"{MONTH_NAMES[month_idx - 1]} {year_idx} — colored dots show each person's church.")
    st.markdown(calendar_legend_html(), unsafe_allow_html=True)

    overflow_days = calendar_overflow_by_day(events_by_day)
    if overflow_days:
        render_info_callout(
            "Some days have more than three events. Open Additional events this month below to see them all.",
            icon="📅",
        )

    st.markdown(
        render_calendar_grid_html(year_idx, month_idx, events_by_day, today),
        unsafe_allow_html=True,
    )
    render_calendar_overflow(overflow_days)


def page_community_map(aggregate_df, map_df):
    render_page_header(
        "🗺️ Community Map",
        "Church locations plus a blurred community density overlay. Heat areas show "
        "approximate regional presence (~8–10 mile zones) — never exact home addresses.",
        question="Where is our community concentrated?",
    )

    with st.sidebar.expander("Map filters", expanded=True):
        church_filter = st.radio("Show churches", ["All", "Filam", "Pillar"], horizontal=True, key="pub_map_church")
        st.caption("The filter applies to both the map and the city chart below.")

    cache = run_map_geocoding_if_needed(map_df)
    church_filter_list = None if church_filter == "All" else [church_filter]
    church_df = build_church_map_data(cache, church_filter_list)
    density_df = build_public_density_data(map_df, cache, church_filter)
    mapped, total = geocode_missing_count(map_df)

    render_info_callout(
        "Gold markers are our church buildings. Soft blue heat shows approximate neighborhood "
        "presence — never individual home addresses.",
        icon="🗺️",
    )

    if church_df.empty and density_df.empty:
        st.info(
            "The map will appear once church and community locations are ready. "
            "Check back soon!"
        )
    else:
        if church_df.empty:
            st.info("Church locations are being prepared. The community heatmap may still appear below.")
        elif density_df.empty:
            if mapped < total:
                st.info(
                    "Community heatmap is still loading — wait a minute and reopen this page, "
                    "or ask staff to refresh."
                )
            else:
                st.info("Church buildings are shown. The community heatmap will appear as more areas are mapped.")

        frames = [f for f in (density_df, church_df) if not f.empty]
        center_lat = pd.concat(frames, ignore_index=True)["lat"].mean()
        center_lng = pd.concat(frames, ignore_index=True)["lng"].mean()

        layers = []

        if not density_df.empty:
            layers.append(
                pdk.Layer(
                    "HeatmapLayer",
                    data=density_df,
                    get_position=["lng", "lat"],
                    get_weight="weight",
                    radius_pixels=180,
                    intensity=0.35,
                    threshold=0.05,
                    opacity=0.65,
                    pickable=False,
                    color_range=[
                        [59, 130, 246, 40],
                        [96, 165, 250, 80],
                        [125, 180, 252, 110],
                        [165, 198, 253, 140],
                        [186, 198, 248, 165],
                        [203, 190, 250, 185],
                    ],
                )
            )

        if not church_df.empty:
            layers.extend([
                pdk.Layer(
                    "ScatterplotLayer",
                    data=church_df,
                    get_position=["lng", "lat"],
                    get_fill_color=[251, 191, 36, 80],
                    get_radius=1,
                    radius_scale=1,
                    radius_min_pixels=30,
                    radius_max_pixels=30,
                    pickable=False,
                ),
                pdk.Layer(
                    "ScatterplotLayer",
                    data=church_df,
                    get_position=["lng", "lat"],
                    get_fill_color="fill_color",
                    get_radius=1,
                    radius_scale=1,
                    radius_min_pixels=16,
                    radius_max_pixels=16,
                    stroked=True,
                    get_line_color="border_color",
                    line_width_min_pixels=4,
                    pickable=True,
                ),
                pdk.Layer(
                    "TextLayer",
                    data=church_df,
                    get_position=["lng", "lat"],
                    get_text="label",
                    get_size=14,
                    get_color="label_color",
                    get_angle=0,
                    get_text_anchor="'middle'",
                    get_alignment_baseline="'bottom'",
                    get_pixel_offset=[0, -22],
                ),
            ])

        st.pydeck_chart(
            pdk.Deck(
                layers=layers,
                initial_view_state=pdk.ViewState(
                    latitude=center_lat,
                    longitude=center_lng,
                    zoom=8,
                    max_zoom=10,
                    min_zoom=6,
                    pitch=0,
                ),
                tooltip={
                    "html": "<b>{members}</b><br/>This is one of our church buildings.",
                    "style": {"backgroundColor": "#1f2937", "color": "white"},
                },
                map_provider="carto",
                map_style="light",
            ),
            width="stretch",
        )

        legend = (
            f"**Legend:** "
            f"<span style='color:{CHURCH_COLORS['Filam']}'>●</span> {church_full_name('Filam')} · "
            f"<span style='color:{CHURCH_COLORS['Pillar']}'>●</span> {church_full_name('Pillar')} · "
            "⛪ Gold markers = church buildings"
        )
        if not density_df.empty:
            legend += " · 🌡️ Soft heat = approximate area presence (neighborhood zones, not homes)"
        st.markdown(legend, unsafe_allow_html=True)

    city_df = city_church_breakdown(aggregate_df)
    if church_filter != "All":
        city_df = city_df[city_df["Church_Affiliation"] == church_filter]

    if city_df.empty:
        st.info("No city data available.")
        return

    top_cities = (
        city_df.groupby("City")["count"]
        .sum()
        .nlargest(12)
        .index.tolist()
    )
    city_df = city_df[city_df["City"].isin(top_cities)]

    def _city_chart():
        fig = px.bar(
            city_df,
            y="City",
            x="count",
            color="Church_Affiliation",
            color_discrete_map=CHURCH_COLORS,
            barmode="stack",
            orientation="h",
            labels={"count": "People", "Church_Affiliation": "Church", "City": "City"},
            text="count",
        )
        fig.update_traces(textposition="inside", textfont=dict(color="#FFFFFF", size=12), insidetextanchor="middle")
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        apply_hover_sentences(fig, "city_bar_stacked")
        show_chart(fig, height=420)

    render_viz_card(
        "Which cities have the most people on the map?",
        "Top 12 cities by headcount, split by church affiliation.",
        _city_chart,
    )


def page_name_lookup(df):
    render_page_header(
        "🔍 Name Lookup",
        "Search by first or last name to find someone's church affiliation.",
        question="Who belongs to which church?",
    )

    public_df = get_public_df(df)

    with st.sidebar.expander("Search", expanded=True):
        search = st.text_input("Search", placeholder="First or last name...", key="pub_search")
        st.caption("Type a first or last name. Leave blank to browse everyone.")
        churches = st.multiselect(
            "Church",
            options=sorted(public_df["Church_Affiliation"].unique()),
            default=sorted(public_df["Church_Affiliation"].unique()),
            key="pub_churches",
        )
        sort_by = st.selectbox("Sort by", ["Last Name", "First Name", "Church"], key="pub_sort")

    filtered = filter_people(
        public_df,
        search,
        churches,
        sort_by=sort_by,
        search_address=False,
    )

    st.markdown(f"**Showing {len(filtered)} of {len(public_df)} people**")

    if filtered.empty:
        st.info("No people match your search. Try a shorter name or clear the church filter.")
        return

    render_lookup_table(filtered.to_dict("records"))
