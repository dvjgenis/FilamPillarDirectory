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
    get_church_addresses,
    get_events_for_month,
    get_public_df,
    get_today_events,
    get_upcoming_events,
    load_geocode_cache,
    month_event_counts_by_church,
    sanitize_events_for_public,
)
from views.shared import (
    calendar_overflow_by_day,
    render_calendar_controls,
    render_calendar_grid_html,
    render_calendar_overflow,
    render_page_header,
    show_chart,
)


def page_overview(df, events):
    render_page_header(
        "📊 Community Overview",
        "Community-wide totals and trends — charts show grouped counts, not individual profiles. "
        "No contact details or home addresses appear here.",
    )

    col1, col2 = st.columns(2)
    col1.metric("People", len(df))
    col2.metric("Churches", df["Church_Affiliation"].nunique())

    c1, c2 = st.columns(2)

    with c1:
        church_counts = df["Church_Affiliation"].value_counts().reset_index()
        church_counts.columns = ["Church", "Count"]
        fig = px.pie(
            church_counts,
            names="Church",
            values="Count",
            color="Church",
            color_discrete_map=CHURCH_COLORS,
            hole=0.45,
            title="Church Affiliation",
        )
        show_chart(fig, pie=True, title="Church Affiliation")

    with c2:
        city_counts = df["City"].value_counts().head(10).reset_index()
        city_counts.columns = ["City", "People"]
        fig = px.bar(
            city_counts,
            x="People",
            y="City",
            orientation="h",
            title="Top 10 Cities",
            color_discrete_sequence=["#6366F1"],
            text="People",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(yaxis=dict(autorange="reversed"))
        show_chart(fig, height=400, title="Top 10 Cities")

    st.subheader("Celebrations by Month")
    hc1, hc2 = st.columns(2)

    with hc1:
        bday_counts = month_event_counts_by_church(events, "birthday")
        fig = px.bar(
            bday_counts,
            x="month_name",
            y="count",
            color="church",
            color_discrete_map=CHURCH_COLORS,
            barmode="stack",
            labels={"month_name": "", "count": "Count", "church": "Church"},
            title="Birthdays by Month",
        )
        show_chart(fig, height=300, title="Birthdays by Month")

    with hc2:
        anniv_counts = month_event_counts_by_church(events, "anniversary")
        fig = px.bar(
            anniv_counts,
            x="month_name",
            y="count",
            color="church",
            color_discrete_map=CHURCH_COLORS,
            barmode="stack",
            labels={"month_name": "", "count": "Count", "church": "Church"},
            title="Anniversaries by Month",
        )
        show_chart(fig, height=300, title="Anniversaries by Month")


def page_celebrations(events):
    render_page_header(
        "📅 Celebrations",
        "A month-by-month look at birthdays and anniversaries. Only first names are shown publicly — "
        "use this page to remember and celebrate alongside the community.",
        show_minor_note=True,
    )

    today = date.today()
    public_events = sanitize_events_for_public(events)

    with st.sidebar.expander("Calendar filters", expanded=True):
        event_filter = st.radio("Show", ["Both", "Birthdays", "Anniversaries"], key="pub_event_filter")
        st.divider()
        st.subheader("Upcoming 30 Days")
        upcoming = get_upcoming_events(public_events, today, 30)
        if event_filter == "Birthdays":
            upcoming = [e for e in upcoming if e["type"] == "birthday"]
        elif event_filter == "Anniversaries":
            upcoming = [e for e in upcoming if e["type"] == "anniversary"]

        if upcoming:
            for e in upcoming[:15]:
                icon = "🎂" if e["type"] == "birthday" else "💍"
                safe_name = html.escape(e["name"])
                st.markdown(
                    f"{icon} **{safe_name}**  \n"
                    f"<span class='metric-sub'>{MONTH_NAMES[e['month']-1]} {e['day']} "
                    f"({e['days_away']}d away)</span>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No upcoming events in the next 30 days.")

    today_events = get_today_events(public_events, today)
    if today_events:
        names = ", ".join(
            f"{'🎂' if e['type'] == 'birthday' else '💍'} {html.escape(e['name'])}" for e in today_events
        )
        st.success(f"**Today ({today.strftime('%B %d')}):** {names}")

    month_idx, year_idx = render_calendar_controls(today)

    month_events = get_events_for_month(public_events, month_idx)
    if event_filter == "Birthdays":
        month_events = [e for e in month_events if e["type"] == "birthday"]
    elif event_filter == "Anniversaries":
        month_events = [e for e in month_events if e["type"] == "anniversary"]

    events_by_day: dict[int, list] = {}
    for e in month_events:
        events_by_day.setdefault(e["day"], []).append(e)

    st.subheader(f"{MONTH_NAMES[month_idx - 1]} {year_idx}")
    st.markdown(
        f"<span style='color:{CHURCH_COLORS['Filam']}'>●</span> {church_full_name('Filam')} &nbsp;&nbsp; "
        f"<span style='color:{CHURCH_COLORS['Pillar']}'>●</span> {church_full_name('Pillar')} &nbsp;&nbsp; "
        "🎂name🎂 = Birthday &nbsp;&nbsp; 💍name💍 = Anniversary",
        unsafe_allow_html=True,
    )
    st.markdown(
        render_calendar_grid_html(year_idx, month_idx, events_by_day, today),
        unsafe_allow_html=True,
    )
    render_calendar_overflow(calendar_overflow_by_day(events_by_day))


def page_community_map(aggregate_df, map_df):
    render_page_header(
        "🗺️ Community Map",
        "Church locations plus a blurred community density overlay. "
        "Heat areas show approximate regional presence (~8–10 mile zones) — never exact home addresses.",
    )

    with st.sidebar.expander("Map filters", expanded=True):
        church_filter = st.radio("Show churches", ["All", "Filam", "Pillar"], horizontal=True, key="pub_map_church")

    cache = load_geocode_cache(warn_on_corrupt=True)
    church_filter_list = None if church_filter == "All" else [church_filter]
    church_df = build_church_map_data(cache, church_filter_list)
    density_df = build_public_density_data(map_df, cache, church_filter)

    household_addresses = sorted(
        set(a for a in map_df["Home_Address"].dropna().unique() if display_value(a) != "Not available")
    )
    mapped_households = sum(
        1 for a in household_addresses if cache.get(a, {}).get("lat") is not None
    )
    if household_addresses:
        st.caption(
            f"Community heatmap coverage: {mapped_households} of {len(household_addresses)} "
            "household areas mapped (staff geocoding)."
        )

    if church_df.empty and density_df.empty:
        st.info(
            "Church building markers appear once geocoded. "
            "The community heatmap is added after staff run household geocoding from the admin map."
        )
    else:
        if church_df.empty:
            st.info("Church locations are being prepared. The heatmap may still appear below.")
        elif density_df.empty:
            st.info(
                "Church locations shown. Community heatmap appears after staff geocode household addresses."
            )

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
                    # Large radius keeps blobs neighborhood-scale even near max zoom
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
                    # Cap zoom so street-level house footprints can't be matched to heat
                    max_zoom=10,
                    min_zoom=6,
                    pitch=0,
                ),
                tooltip={
                    "html": "<b>{members}</b>",
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

    st.subheader("People by City")
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

    fig = px.bar(
        city_df,
        y="City",
        x="count",
        color="Church_Affiliation",
        color_discrete_map=CHURCH_COLORS,
        barmode="stack",
        orientation="h",
        labels={"count": "People", "Church_Affiliation": "Church"},
        title="Top 12 Cities by Church",
        text="count",
    )
    fig.update_traces(
        textposition="inside",
        textfont=dict(color="#FFFFFF", size=12),
        insidetextanchor="middle",
    )
    fig.update_layout(yaxis=dict(categoryorder="total ascending"))
    show_chart(fig, height=420, title="Top 12 Cities by Church")


def page_name_lookup(df):
    render_page_header(
        "🔍 Name Lookup",
        "Search by first or last name to find someone's church affiliation. "
        "Only name and church are listed — no phone, email, address, or family details.",
    )

    public_df = get_public_df(df)

    with st.sidebar.expander("Search", expanded=True):
        search = st.text_input("Search", placeholder="First or last name...", key="pub_search")
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
        st.info("No people match your search.")
        return

    display_df = filtered.copy()
    display_df["Church_Affiliation"] = display_df["Church_Affiliation"].apply(display_value)
    display_df = display_df.rename(columns={
        "First_Name": "First Name",
        "Last_Name": "Last Name",
        "Church_Affiliation": "Church",
    })
    st.dataframe(
        display_df[["First Name", "Last Name", "Church"]],
        hide_index=True,
        width="stretch",
    )
