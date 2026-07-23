"""Admin-only dashboard pages with full directory access."""

from __future__ import annotations

import html
from datetime import date

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from helpers import (
    ALL_DISPLAY_FIELDS,
    CHURCH_COLORS,
    CSV_PATH,
    MONTH_NAMES,
    audit_data_quality,
    background_geocoding_running,
    build_church_map_data,
    build_map_data,
    compute_regional_view_state,
    church_full_name,
    church_color_legend_html,
    city_church_breakdown,
    csv_mtime,
    display_value,
    event_icon,
    filter_people,
    format_phone,
    geocode_addresses,
    collect_directory_addresses,
    deck_layer_records,
    household_map_radius_pixels,
    get_events_for_month,
    get_today_events,
    get_upcoming_events,
    household_size_counts,
    is_birthday_event,
    is_valid_mmdd,
    load_geocode_cache,
    month_event_counts_by_church,
    person_key,
    prepare_map_frame,
)
from views.shared import (
    apply_hover_sentences,
    build_regional_deck_view,
    calendar_legend_html,
    calendar_overflow_by_day,
    church_badge_html,
    render_calendar_controls,
    render_calendar_grid_html,
    render_calendar_overflow,
    render_info_callout,
    render_metric_row,
    render_page_header,
    render_viz_card,
    show_chart,
)

CARD_PAGE_SIZE = 24


def render_admin_person_card(person: dict):
    """Render a person card using native Streamlit."""
    with st.container(border=True):
        st.markdown(f"**{display_value(person.get('Full_Name'))}**")
        st.markdown(
            church_badge_html(person.get("Church_Affiliation", "")),
            unsafe_allow_html=True,
        )

        if is_valid_mmdd(person.get("Birthday")):
            st.caption(f"🎂 Birthday: {display_value(person['Birthday'])}")
        if is_valid_mmdd(person.get("Wedding_Anniversary")):
            st.caption(f"💍 Anniversary: {display_value(person['Wedding_Anniversary'])}")

        city = display_value(person.get("City"))
        state = display_value(person.get("State"))
        location = f"{city}, {state}" if city != "Not available" else state
        st.caption(f"📍 {location}")
        st.caption(f"📞 {format_phone(person.get('Phone_Number'))}")

        spouse = display_value(person.get("Spouse_Name"))
        if spouse != "Not available":
            st.caption(f"💑 Spouse: {spouse}")

        children_names = display_value(person.get("Children_Names"))
        children_bdays = display_value(person.get("Children_Birthdays"))
        if children_names != "Not available":
            st.caption(f"👨‍👩‍👧 Children: {children_names}")
        if children_bdays != "Not available":
            st.caption(f"🎂 Children birthdays: {children_bdays}")

        member_icon = "✅ Member" if person.get("Is_Member") else "➖ Non-member"
        opt_icon = "📢 Opted in" if person.get("Opt_In_Announcements") else "🔇 Not opted in"
        st.caption(f"{member_icon} · {opt_icon}")


def render_person_detail(p):
    """Render full person detail with all 15 CSV fields."""
    st.markdown(f"### {display_value(p['Full_Name'])}")
    st.markdown(church_badge_html(p["Church_Affiliation"]), unsafe_allow_html=True)

    field_labels = {
        "Church_Affiliation": "Church",
        "First_Name": "First Name",
        "Last_Name": "Last Name",
        "Birthday": "Birthday",
        "Home_Address": "Home Address",
        "Phone_Number": "Phone",
        "Email_Address": "Email",
        "Wedding_Anniversary": "Wedding Anniversary",
        "Spouse_Name": "Spouse Name",
        "Spouse_Birthday": "Spouse Birthday",
        "Spouse_Phone": "Spouse Phone",
        "Children_Names": "Children Names",
        "Children_Birthdays": "Children Birthdays",
        "Is_Member": "Member",
        "Opt_In_Announcements": "Opt-in Announcements",
    }

    c1, c2 = st.columns(2)
    left_fields = ALL_DISPLAY_FIELDS[:8]
    right_fields = ALL_DISPLAY_FIELDS[8:]

    with c1:
        for field in left_fields:
            value = p[field]
            if field in ("Phone_Number", "Spouse_Phone"):
                rendered = format_phone(value)
            elif field == "Church_Affiliation":
                rendered = church_full_name(display_value(value))
            else:
                rendered = display_value(value)
            st.write(f"**{field_labels[field]}:** {rendered}")

    with c2:
        for field in right_fields:
            value = p[field]
            if field == "Spouse_Phone":
                rendered = format_phone(value)
            elif field in ("Is_Member", "Opt_In_Announcements"):
                rendered = "Yes" if value else "No"
            else:
                rendered = display_value(value)
            st.write(f"**{field_labels[field]}:** {rendered}")

        city_state = f"{display_value(p.get('City'))}, {display_value(p.get('State'))}"
        st.write(f"**City / State:** {city_state}")


@st.dialog("Person details")
def person_detail_dialog(person: dict) -> None:
    render_person_detail(person)


def _directory_table_df(filtered: pd.DataFrame) -> pd.DataFrame:
    table = filtered.copy()
    table["Phone"] = table["Phone_Number"].apply(format_phone)
    table["Member"] = table["Is_Member"].map({True: "Yes", False: "No"})
    table["Opt-in"] = table["Opt_In_Announcements"].map({True: "Yes", False: "No"})
    table["City"] = table["City"].apply(display_value)
    return table[
        ["Full_Name", "Church_Affiliation", "Phone", "City", "Member", "Opt-in"]
    ].rename(columns={
        "Full_Name": "Name",
        "Church_Affiliation": "Church",
    })


def _render_card_pagination(total_items: int, page_key: str) -> tuple[int, int, int]:
    total_pages = max(1, (total_items + CARD_PAGE_SIZE - 1) // CARD_PAGE_SIZE)
    if page_key not in st.session_state:
        st.session_state[page_key] = 0
    page = min(st.session_state[page_key], total_pages - 1)
    st.session_state[page_key] = page

    nav1, nav2, nav3 = st.columns([1, 2, 1])
    with nav1:
        if st.button("◀ Prev", key=f"{page_key}_prev", disabled=page == 0):
            st.session_state[page_key] = page - 1
            st.rerun()
    with nav2:
        st.caption(f"Page {page + 1} of {total_pages}")
    with nav3:
        if st.button("Next ▶", key=f"{page_key}_next", disabled=page >= total_pages - 1):
            st.session_state[page_key] = page + 1
            st.rerun()

    start = page * CARD_PAGE_SIZE
    end = min(start + CARD_PAGE_SIZE, total_items)
    return page, start, end


def page_directory(df, households):
    render_page_header(
        "👥 People Directory",
        "Search and browse every directory entry with full contact and family details.",
        question="Who is in our directory?",
    )

    render_info_callout(
        "Search, filter, or switch between Table, Cards, and Households views. "
        "Open a person to see all 15 fields, or download a CSV export.",
        icon="👥",
    )

    with st.sidebar.expander("Filters", expanded=True):
        search = st.text_input("Search", placeholder="Name or address...", key="adm_search")
        churches = st.multiselect(
            "Church",
            options=sorted(df["Church_Affiliation"].unique()),
            default=sorted(df["Church_Affiliation"].unique()),
            key="adm_churches",
        )
        member_filter = st.selectbox("Membership", ["All", "Members", "Non-Members"], key="adm_member")
        opt_in_filter = st.selectbox("Announcements", ["All", "Opted In", "Not Opted In"], key="adm_optin")
        sort_by = st.selectbox("Sort by", ["Last Name", "First Name", "Church"], key="adm_sort")

    filtered = filter_people(df, search, churches, member_filter, opt_in_filter, sort_by)
    filtered_addresses = set(filtered["Home_Address"].dropna())
    filtered_households = [h for h in households if h["address"] in filtered_addresses]

    view_mode = st.radio(
        "View",
        ["Table", "Cards", "Households"],
        horizontal=True,
        key="adm_view_mode",
    )

    header_col, download_col = st.columns([4, 1])
    with header_col:
        st.markdown(
            f"**Showing {len(filtered)} of {len(df)} people** · "
            f"**{len(filtered_households)} households**"
        )
    with download_col:
        export_df = filtered[ALL_DISPLAY_FIELDS].copy()
        for col in export_df.columns:
            if col in ("Phone_Number", "Spouse_Phone"):
                export_df[col] = export_df[col].apply(format_phone)
            elif col in ("Is_Member", "Opt_In_Announcements"):
                export_df[col] = export_df[col].map({True: "Yes", False: "No"})
            else:
                export_df[col] = export_df[col].apply(display_value)
        st.download_button(
            "Download CSV",
            data=export_df.to_csv(index=False),
            file_name="church_directory_filtered.csv",
            mime="text/csv",
            width="stretch",
        )

    if filtered.empty:
        st.info("No people match your filters.")
        return

    keyed_people = filtered.copy()
    keyed_people["_person_key"] = keyed_people.apply(person_key, axis=1)
    key_labels = {
        row["_person_key"]: f"{row['Full_Name']} — {display_value(row.get('Home_Address'))}"
        for _, row in keyed_people.iterrows()
    }

    if view_mode == "Table":
        st.dataframe(_directory_table_df(filtered), hide_index=True, width="stretch")

        detail_col1, detail_col2 = st.columns([3, 1])
        with detail_col1:
            selected_key = st.selectbox(
                "Open details for",
                options=list(key_labels.keys()),
                format_func=lambda k: key_labels[k],
                key="adm_person_key",
            )
        with detail_col2:
            st.write("")
            st.write("")
            if st.button("View details", key="adm_view_detail", width="stretch"):
                person = keyed_people[keyed_people["_person_key"] == selected_key].iloc[0].to_dict()
                person_detail_dialog(person)

    elif view_mode == "Cards":
        _, start, end = _render_card_pagination(len(filtered), "adm_card_page")
        page_rows = filtered.iloc[start:end]
        cols = st.columns(3)
        for i, (_, person) in enumerate(page_rows.iterrows()):
            with cols[i % 3]:
                render_admin_person_card(person.to_dict())

        detail_key = st.selectbox(
            "Open details for",
            options=list(key_labels.keys()),
            format_func=lambda k: key_labels[k],
            key="adm_card_person_key",
        )
        if st.button("View details", key="adm_card_view_detail"):
            person = keyed_people[keyed_people["_person_key"] == detail_key].iloc[0].to_dict()
            person_detail_dialog(person)

    else:
        visible_households = [
            hh for hh in filtered_households
            if any(m["Full_Name"] in set(filtered["Full_Name"]) for m in hh["members"])
        ]
        _, start, end = _render_card_pagination(len(visible_households), "adm_hh_page")
        for hh in visible_households[start:end]:
            hh_members = [m for m in hh["members"] if m["Full_Name"] in set(filtered["Full_Name"])]
            if not hh_members:
                continue
            st.markdown(
                f"### 🏠 {display_value(hh['address'])} ({len(hh_members)} people)"
            )
            cols = st.columns(3)
            for i, person in enumerate(hh_members):
                with cols[i % 3]:
                    render_admin_person_card(person)


def _geocode_coverage(addresses: list[str], cache: dict) -> tuple[int, int]:
    mapped = sum(1 for a in addresses if cache.get(a, {}).get("lat") is not None)
    return mapped, len(addresses)


def page_map(df, households):
    render_page_header(
        "🗺️ Where We Live",
        "Household locations worldwide. Dot color shows primary church affiliation; "
        "dot size reflects household size. The map opens on Chicagoland — zoom and pan to explore. "
        "Markers with church labels are building locations.",
        question="Where do households live?",
    )

    addresses = collect_directory_addresses(df)

    with st.sidebar.expander("Map filters", expanded=True):
        church_filter = st.radio(
            "Show churches",
            ["All", *CHURCH_COLORS.keys()],
            horizontal=True,
            key="adm_map_church",
        )

    cache = load_geocode_cache(warn_on_corrupt=True)
    mapped, total = _geocode_coverage(addresses, cache)

    missing = [a for a in addresses if a not in cache or cache[a].get("lat") is None]
    failed = [a for a in addresses if cache.get(a, {}).get("error")]

    if missing and background_geocoding_running():
        st.info(
            f"Household addresses are still being mapped in the background "
            f"({mapped} of {total} ready). You can use other pages and return here in a "
            "few minutes, or refresh this page for updates."
        )
    elif missing and mapped < total:
        st.info(
            f"Mapping is in progress or not complete ({mapped} of {total} ready). "
            "Check back shortly, refresh this page, or use the tools below to geocode manually."
        )

    with st.expander("Map tools (geocoding & coverage)", expanded=bool(missing) and not background_geocoding_running()):
        st.metric("Addresses mapped", f"{mapped} of {total}")
        if missing:
            st.warning(
                f"**{len(missing)}** address(es) could not be mapped yet. "
                "Mapping runs in the background after you sign in. "
                "Try **Refresh data** in the sidebar, or geocode manually below."
            )
            geo_col1, geo_col2 = st.columns(2)
            with geo_col1:
                if st.button("Geocode all missing", key="adm_geocode"):
                    progress = st.progress(0)
                    status = st.empty()

                    def on_progress(current, total_count, addr, cached=False):
                        progress.progress(current / total_count)
                        label = "cached" if cached else "geocoding"
                        status.text(f"{label}: {addr} ({current}/{total_count})")

                    with st.spinner("Geocoding addresses via OpenStreetMap..."):
                        cache, failed_run = geocode_addresses(missing, on_progress)

                    if failed_run:
                        st.error(f"Failed to geocode {len(failed_run)} address(es):")
                        st.dataframe(pd.DataFrame({"Address": failed_run}), hide_index=True)
                    else:
                        st.success("All requested addresses geocoded successfully!")
                    st.rerun()
            with geo_col2:
                if failed and st.button("Retry failed only", key="adm_geocode_retry"):
                    progress = st.progress(0)
                    status = st.empty()

                    def on_progress(current, total_count, addr, cached=False):
                        progress.progress(current / total_count)
                        label = "cached" if cached else "geocoding"
                        status.text(f"{label}: {addr} ({current}/{total_count})")

                    with st.spinner("Retrying failed addresses..."):
                        cache, failed_run = geocode_addresses(failed, on_progress)
                    if failed_run:
                        st.error(f"Still failed: {len(failed_run)} address(es)")
                    else:
                        st.success("Retry complete!")
                    st.rerun()
        else:
            st.success("All addresses are mapped.")

        unmapped = [a for a in addresses if a not in cache or cache[a].get("lat") is None]
        if unmapped:
            st.markdown(f"**{len(unmapped)} unmapped address(es)**")
            st.dataframe(pd.DataFrame({"Address": unmapped}), hide_index=True)

    cache = load_geocode_cache()
    map_df = prepare_map_frame(build_map_data(households, cache))
    church_filter_list = None if church_filter == "All" else [church_filter]
    church_df = prepare_map_frame(build_church_map_data(cache, church_filter_list))

    if church_filter != "All":
        map_df = map_df[map_df["church"] == church_filter]

    if map_df.empty and church_df.empty:
        st.info("No geocoded locations yet. Reload the app or use **Refresh data** to geocode addresses.")
        return

    if map_df.empty and not church_df.empty:
        st.info(f"No household addresses for {church_filter}, showing church location only.")

    render_info_callout(
        "Each dot is a household. Dot size shows how many people live there (larger = more people). "
        "Labeled markers are church buildings. Hover a dot to see the address and members.",
        icon="📍",
    )

    view_state = compute_regional_view_state(map_df, church_df)
    initial_view_state, map_views = build_regional_deck_view(view_state)

    layers = []
    if not map_df.empty:
        for household_size in sorted(map_df["size"].unique()):
            subset = map_df[map_df["size"] == household_size]
            radius = household_map_radius_pixels(int(household_size))
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=deck_layer_records(subset),
                    get_position=["lng", "lat"],
                    get_fill_color="color",
                    get_radius=radius,
                    radius_units="pixels",
                    radius_scale=1,
                    radius_min_pixels=radius,
                    radius_max_pixels=radius,
                    pickable=True,
                )
            )

    if not church_df.empty:
        church_data = deck_layer_records(church_df)
        layers.extend([
            pdk.Layer(
                "ScatterplotLayer",
                data=church_data,
                get_position=["lng", "lat"],
                get_fill_color=[251, 191, 36, 80],
                get_radius=14,
                radius_units="pixels",
                radius_scale=1,
                radius_min_pixels=14,
                radius_max_pixels=14,
                pickable=False,
            ),
            pdk.Layer(
                "ScatterplotLayer",
                data=church_data,
                get_position=["lng", "lat"],
                get_fill_color="fill_color",
                get_radius=9,
                radius_units="pixels",
                radius_scale=1,
                radius_min_pixels=9,
                radius_max_pixels=9,
                stroked=True,
                get_line_color="border_color",
                line_width_min_pixels=4,
                pickable=True,
            ),
            pdk.Layer(
                "TextLayer",
                data=church_data,
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
            views=map_views,
            initial_view_state=initial_view_state,
            tooltip={
                "html": (
                    "<b>{members}</b><br/>"
                    "This household lives at {address}.<br/>"
                    "Church: {church} · {size} people in household."
                ),
                "style": {"backgroundColor": "#1f2937", "color": "white"},
            },
            map_provider="carto",
            map_style="light",
        ),
        width="stretch",
    )

    st.markdown(
        f"**Legend:** {church_color_legend_html()} · "
        "⛪ Church building markers · "
        "Dot size = people in household (larger families = bigger dots)",
        unsafe_allow_html=True,
    )

    if len(map_df) > 1:
        lat_spread = map_df["lat"].max() - map_df["lat"].min()
        lng_spread = map_df["lng"].max() - map_df["lng"].min()
        st.caption(
            f"Community spans ~{lat_spread * 69:.0f} miles north-south "
            f"and ~{lng_spread * 54:.0f} miles east-west from centroid."
        )

    st.subheader("People by City")
    city_df = city_church_breakdown(df)
    if church_filter != "All":
        city_df = city_df[city_df["Church_Affiliation"] == church_filter]

    top_cities = city_df.groupby("City")["count"].sum().nlargest(12).index.tolist()
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
        fig.update_traces(
            textposition="inside",
            textfont=dict(color="#FFFFFF", size=12),
            insidetextanchor="middle",
        )
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        apply_hover_sentences(fig, "city_bar_stacked")
        show_chart(fig, height=420)

    render_viz_card(
        "Which cities have the most people by church?",
        "Top 12 cities by headcount, stacked by church affiliation.",
        _city_chart,
    )


def _event_label(event) -> str:
    """Prefer display_name when set; fall back to name (handles NaN from DataFrame rows)."""
    if hasattr(event, "get"):
        display = event.get("display_name")
        name = event.get("name", "")
    else:
        display = event["display_name"] if "display_name" in event else None
        name = event["name"]

    if display is not None and pd.notna(display) and str(display).strip():
        return str(display)
    return str(name)


def _filter_admin_events(events: list[dict], event_filter: str) -> list[dict]:
    if event_filter == "Birthdays":
        return [e for e in events if is_birthday_event(e)]
    if event_filter == "Adult Birthdays":
        return [e for e in events if e["type"] == "birthday"]
    if event_filter == "Children's Birthdays":
        return [e for e in events if e["type"] == "child_birthday"]
    if event_filter == "Anniversaries":
        return [e for e in events if e["type"] == "anniversary"]
    return events


def page_calendar(df, events):
    render_page_header(
        "📅 Birthdays & Anniversaries",
        "Full-name calendar for staff planning and pastoral care — includes children's birthdays "
        "listed on parent records alongside each adult's own birthday entry.",
        question="Who should we celebrate this month?",
    )

    today = date.today()

    with st.sidebar.expander("Calendar filters", expanded=True):
        event_filter = st.radio(
            "Show",
            ["Both", "Birthdays", "Adult Birthdays", "Children's Birthdays", "Anniversaries"],
            key="adm_event_filter",
        )
        st.divider()
        st.subheader("Upcoming 30 Days")
        upcoming = _filter_admin_events(get_upcoming_events(events, today, 30), event_filter)

        if upcoming:
            for e in upcoming[:20]:
                safe_label = html.escape(_event_label(e))
                st.markdown(
                    f"{event_icon(e['type'])} **{safe_label}**  \n"
                    f"<span class='metric-sub'>{MONTH_NAMES[e['month']-1]} {e['day']} "
                    f"({e['days_away']}d away)</span>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No upcoming events in the next 30 days.")

    today_events = _filter_admin_events(get_today_events(events, today), event_filter)
    if today_events:
        names = ", ".join(
            f"{event_icon(e['type'])} {html.escape(_event_label(e))}" for e in today_events
        )
        st.success(f"**Today ({today.strftime('%B %d')}):** {names}")

    month_idx, year_idx = render_calendar_controls(today, mode="staff")

    month_events = _filter_admin_events(get_events_for_month(events, month_idx), event_filter)

    events_by_day: dict[int, list] = {}
    for e in month_events:
        events_by_day.setdefault(e["day"], []).append(e)

    st.markdown(
        '<p class="viz-question">Who are we celebrating this month?</p>',
        unsafe_allow_html=True,
    )
    st.subheader(f"{MONTH_NAMES[month_idx - 1]} {year_idx}")
    st.markdown(calendar_legend_html(include_children=True), unsafe_allow_html=True)
    st.markdown(
        render_calendar_grid_html(year_idx, month_idx, events_by_day, today),
        unsafe_allow_html=True,
    )
    render_calendar_overflow(calendar_overflow_by_day(events_by_day))

    if month_events:
        def _timeline_chart():
            timeline_df = pd.DataFrame(month_events)
            timeline_df["label"] = timeline_df.apply(_event_label, axis=1)
            timeline_df["event_type"] = timeline_df["type"].map({
                "birthday": "Adult Birthday",
                "child_birthday": "Child Birthday",
                "anniversary": "Anniversary",
            })
            fig = px.scatter(
                timeline_df,
                x="day",
                y="event_type",
                color="church",
                hover_name="label",
                color_discrete_map=CHURCH_COLORS,
                labels={"day": "Day of Month", "event_type": "Event Type", "church": "Church"},
            )
            fig.update_traces(
                marker=dict(size=14),
                hovertemplate=(
                    "<b>%{hovertext}</b> on day %{x} (%{fullData.name}).<extra></extra>"
                ),
            )
            show_chart(fig, height=280)

        render_viz_card(
            "When do events cluster during this month?",
            "Each dot is one celebration. Hover to see the full name and church.",
            _timeline_chart,
        )
    else:
        st.info(f"No events in {MONTH_NAMES[month_idx - 1]} with current filters.")


def _render_data_quality_section(df, households) -> None:
    from data_source import data_source_label, sheet_cache_ttl, uses_google_sheets

    issues = audit_data_quality(df)
    cache = load_geocode_cache()
    addresses = collect_directory_addresses(df)
    mapped, total = _geocode_coverage(addresses, cache)
    issue_count = (
        len(issues["missing_phones"])
        + len(issues["missing_emails"])
        + len(issues["missing_birthdays"])
        + len(issues["children_mismatches"])
        + len(issues["stale_children_listings"])
    )

    if uses_google_sheets():
        source_label = f"{data_source_label()} · refreshes every {sheet_cache_ttl()}s"
    elif CSV_PATH.exists():
        from datetime import datetime

        source_label = f"CSV last modified: {datetime.fromtimestamp(csv_mtime()).strftime('%Y-%m-%d %H:%M')}"
    else:
        source_label = "Data source: unknown"

    label = f"Data Quality ({issue_count} issue{'s' if issue_count != 1 else ''})" if issue_count else "Data Quality"
    with st.expander(label, expanded=False):
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Missing phones", len(issues["missing_phones"]))
        q2.metric("Missing emails", len(issues["missing_emails"]))
        q3.metric("Missing birthdays", len(issues["missing_birthdays"]))
        q4.metric("Geocoded", f"{mapped}/{total}")

        st.caption(source_label)

        if issues["children_mismatches"]:
            st.markdown("**Children name/birthday mismatches**")
            for item in issues["children_mismatches"]:
                st.markdown(f"- {html.escape(item)}")

        if issues["stale_children_listings"]:
            st.markdown("**Stale children listings**")
            st.caption(
                "These children have their own directory entry — remove them from the parent's "
                "Children_Names field to avoid duplicate calendar data."
            )
            for item in issues["stale_children_listings"]:
                st.markdown(f"- {html.escape(item)}")


def page_insights(df, households, events):
    render_page_header(
        "📊 Community Insights",
        "Internal statistics on membership, opt-in rates, household sizes, and data completeness. "
        "Useful for leadership overview — not shown on the public portal.",
        question="How healthy is our directory data?",
    )

    _render_data_quality_section(df, households)

    today = date.today()
    week_events = get_upcoming_events(events, today, 7)

    st.subheader("Data Completeness")
    anniv_rate = df["Anniversary_Month"].notna().sum() / len(df) * 100
    member_rate = df["Is_Member"].sum() / len(df) * 100
    optin_rate = df["Opt_In_Announcements"].sum() / len(df) * 100
    render_metric_row([
        ("Anniversary Data", f"{anniv_rate:.0f}%", "Share of people with an anniversary on file."),
        ("Membership Rate", f"{member_rate:.0f}%", "Share of people marked as members."),
        ("Announcement Opt-in", f"{optin_rate:.0f}%", "Share of people opted into announcements."),
    ])

    if week_events:
        st.subheader("This Week")
        with st.container(height=200):
            for e in week_events:
                days_label = "Today!" if e["days_away"] == 0 else f"in {e['days_away']} days"
                st.markdown(
                    f"{event_icon(e['type'])} **{html.escape(_event_label(e))}** — "
                    f"{MONTH_NAMES[e['month']-1][:3]} {e['day']} ({days_label})"
                )

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
            show_chart(fig, pie=True)

        render_viz_card(
            "How are we split by church?",
            "Each slice is one person in the directory.",
            _church_pie,
        )

    with c2:
        def _membership_chart():
            member_data = (
                df.groupby(["Church_Affiliation", "Is_Member"])
                .size()
                .reset_index(name="Count")
            )
            member_data["Status"] = member_data["Is_Member"].map({True: "Member", False: "Non-Member"})
            fig = px.bar(
                member_data,
                x="Church_Affiliation",
                y="Count",
                color="Status",
                barmode="group",
                color_discrete_map={"Member": "#10B981", "Non-Member": "#9CA3AF"},
                labels={"Church_Affiliation": "Church", "Count": "People", "Status": "Status"},
            )
            apply_hover_sentences(fig, "membership_grouped")
            show_chart(fig)

        render_viz_card(
            "Who is a member at each church?",
            "Grouped bars compare members and non-members side by side.",
            _membership_chart,
        )

    c3, c4 = st.columns(2)

    with c3:
        def _optin_chart():
            opt_data = (
                df.groupby(["Church_Affiliation", "Opt_In_Announcements"])
                .size()
                .reset_index(name="Count")
            )
            opt_data["Status"] = opt_data["Opt_In_Announcements"].map(
                {True: "Opted In", False: "Not Opted In"}
            )
            fig = px.bar(
                opt_data,
                x="Church_Affiliation",
                y="Count",
                color="Status",
                barmode="stack",
                color_discrete_map={"Opted In": "#3B82F6", "Not Opted In": "#D1D5DB"},
                labels={"Church_Affiliation": "Church", "Count": "People", "Status": "Status"},
            )
            apply_hover_sentences(fig, "optin_stacked")
            show_chart(fig)

        render_viz_card(
            "Who opted into announcements?",
            "Stacked bars show opt-in vs. not opted in for each church.",
            _optin_chart,
        )

    with c4:
        def _household_chart():
            size_df = household_size_counts(households)
            fig = px.bar(
                size_df,
                x="size",
                y="count",
                labels={"size": "People per Household", "count": "Households"},
                color_discrete_sequence=["#8B5CF6"],
                text="count",
            )
            fig.update_traces(textposition="outside")
            apply_hover_sentences(fig, "household_size")
            show_chart(fig)

        render_viz_card(
            "How big are our households?",
            "Number of households grouped by how many people live at each address.",
            _household_chart,
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
            "Stacked bars show birthday count per month, by church.",
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
            "Stacked bars show anniversary count per month, by church.",
            _anniv_chart,
        )

    def _top_cities_chart():
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
        _top_cities_chart,
    )
