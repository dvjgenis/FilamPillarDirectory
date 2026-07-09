"""Church Directory — public community portal with in-app staff login."""

from __future__ import annotations

import streamlit as st

from auth import (
    ADMIN_PAGE_LABELS,
    is_admin_authenticated,
    is_admin_page,
    load_authenticator,
    navigation_options,
    render_credentials_setup_banner,
    render_security_warnings,
    render_sidebar_auth,
)
from data_source import (
    directory_cache_key,
    sheet_cache_ttl,
    uses_google_sheets,
)
from helpers import (
    build_admin_events,
    build_events,
    ensure_church_geocoded,
    geocode_cache_mtime,
    get_public_aggregate_df,
    get_public_map_df,
    group_households,
    load_and_clean,
    sanitize_events_for_public,
)
from views.admin_views import (
    page_calendar,
    page_directory,
    page_insights,
    page_map,
)
from views.public_views import (
    page_celebrations,
    page_community_map,
    page_home,
    page_name_lookup,
    page_overview,
)
from views.shared import (
    apply_global_styles,
    apply_pending_navigation,
    render_public_sidebar_welcome,
    render_staff_sidebar_welcome,
)

st.set_page_config(
    page_title="Church Directory",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()
authenticator = load_authenticator()

_CACHE_TTL = sheet_cache_ttl() if uses_google_sheets() else None


@st.cache_data(ttl=_CACHE_TTL)
def _load_directory_core(_cache_key: str):
    df = load_and_clean()
    try:
        ensure_church_geocoded()
    except Exception as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        st.session_state.setdefault("geocode_warning", f"Church locations could not be geocoded: {detail}")
    return df


@st.cache_data(ttl=_CACHE_TTL)
def get_public_data(_cache_key: str, _geocode_mtime: float):
    df = _load_directory_core(_cache_key)
    events = build_events(df)
    public_events = sanitize_events_for_public(events)
    public_df = get_public_aggregate_df(df)
    public_map_df = get_public_map_df(df)
    return public_df, public_events, public_map_df


@st.cache_data(ttl=_CACHE_TTL)
def get_admin_data(_cache_key: str, _geocode_mtime: float):
    df = _load_directory_core(_cache_key)
    households = group_households(df)
    events = build_admin_events(df)
    return df, households, events


def _handle_load_error(exc: Exception) -> None:
    from data_source import format_sheets_load_error

    sheets_message = format_sheets_load_error(exc)
    if sheets_message:
        st.error(sheets_message)
    elif isinstance(exc, FileNotFoundError):
        st.error(str(exc))
    elif isinstance(exc, ValueError):
        st.error(f"Directory data error: {exc}")
    elif isinstance(exc, RuntimeError) and str(exc):
        st.error(str(exc))
    else:
        detail = str(exc).strip() or exc.__class__.__name__
        st.error(f"Failed to load directory data: {detail}")
    st.stop()


def load_public_data():
    """Load cached public data; show friendly errors on failure."""
    try:
        return get_public_data(directory_cache_key(), geocode_cache_mtime())
    except Exception as exc:
        _handle_load_error(exc)


def load_admin_data():
    """Load cached admin data; show friendly errors on failure."""
    try:
        return get_admin_data(directory_cache_key(), geocode_cache_mtime())
    except Exception as exc:
        _handle_load_error(exc)


def render_admin_page(page: str, df, households, events):
    if page == "👥 Directory":
        page_directory(df, households)
    elif page == "🗺️ Household Map":
        page_map(df, households)
    elif page == "📅 Full Calendar":
        page_calendar(df, events)
    elif page == "📊 Insights":
        page_insights(df, households, events)


def render_public_page(page: str, df, events, map_df):
    if page == "🏠 Home":
        page_home(df, events)
    elif page == "📊 Overview":
        page_overview(df, events)
    elif page == "📅 Celebrations":
        page_celebrations(events)
    elif page == "🗺️ Map":
        page_community_map(df, map_df)
    elif page == "🔍 Name Lookup":
        page_name_lookup(df)


def main():
    render_credentials_setup_banner()
    render_security_warnings()

    geocode_warning = st.session_state.pop("geocode_warning", None)
    if geocode_warning:
        st.warning(geocode_warning)

    with st.sidebar:
        st.title("⛪ Church Directory")
        st.caption("Filam & Pillar Community Directory")
        authenticated = render_sidebar_auth(authenticator)

        if authenticated:
            st.caption("Staff mode active")
        else:
            st.caption("Public community portal")

        if uses_google_sheets():
            st.caption(f"Live data · refreshes every {sheet_cache_ttl()}s")

        nav_mode = "staff" if authenticated else "public"
        apply_pending_navigation(f"nav_{nav_mode}")
        options = navigation_options()
        page = st.radio(
            "Navigate",
            options,
            label_visibility="collapsed",
            key=f"nav_{nav_mode}",
        )
        if page not in options:
            page = options[0]

        if authenticated:
            if st.button("Refresh data", key="refresh_data", width="stretch"):
                st.cache_data.clear()
                st.rerun()

        st.divider()
        admin_payload = None
        if authenticated:
            admin_payload = load_admin_data()
            df_admin, households, _ = admin_payload
            col1, col2 = st.columns(2)
            col1.metric("People", len(df_admin))
            col2.metric("Churches", df_admin["Church_Affiliation"].nunique())
            col3, col4 = st.columns(2)
            col3.metric("Households", len(households))
            col4.metric("Members", int(df_admin["Is_Member"].sum()))
            render_staff_sidebar_welcome()
        else:
            render_public_sidebar_welcome()
            st.caption("Limited public view. Use **Staff Login** for full access.")

    if authenticated or is_admin_page(page):
        if not is_admin_authenticated():
            st.warning("Please sign in via **Staff Login** in the sidebar to access this page.")
            st.stop()
        if page not in ADMIN_PAGE_LABELS:
            page = ADMIN_PAGE_LABELS[0]
        if admin_payload is None:
            admin_payload = load_admin_data()
        df, households, events = admin_payload
        render_admin_page(page, df, households, events)
    else:
        df, events, map_df = load_public_data()
        render_public_page(page, df, events, map_df)


if __name__ == "__main__":
    main()
