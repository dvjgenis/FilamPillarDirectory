"""Church Directory — admin-only staff portal."""

from __future__ import annotations

import streamlit as st

from auth import (
    ADMIN_PAGE_LABELS,
    is_authenticated,
    render_credentials_setup_banner,
    render_login_page,
    render_sidebar_logout,
)
from data_source import (
    directory_cache_key,
    sheet_cache_ttl,
    uses_google_sheets,
)
from helpers import (
    background_geocoding_running,
    build_admin_events,
    ensure_church_geocoded,
    geocode_cache_mtime,
    geocode_progress,
    group_households,
    load_and_clean,
    start_background_geocoding,
)
from views.admin_views import (
    page_calendar,
    page_directory,
    page_insights,
    page_map,
)
from views.shared import (
    apply_global_styles,
    apply_pending_navigation,
    render_staff_sidebar_welcome,
)

st.set_page_config(
    page_title="Church Directory",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()

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


def main():
    render_credentials_setup_banner()

    if not is_authenticated():
        render_login_page()
        st.stop()

    geocode_warning = st.session_state.pop("geocode_warning", None)
    if geocode_warning:
        st.warning(geocode_warning)

    with st.sidebar:
        st.title("⛪ Church Directory")
        st.caption("Filam & Pillar Community Directory")
        render_sidebar_logout()
        st.caption("Staff directory")

        if uses_google_sheets():
            st.caption(f"Live data · refreshes every {sheet_cache_ttl()}s")

        apply_pending_navigation("nav_staff")
        page = st.radio(
            "Navigate",
            ADMIN_PAGE_LABELS,
            label_visibility="collapsed",
            key="nav_staff",
        )
        if page not in ADMIN_PAGE_LABELS:
            page = ADMIN_PAGE_LABELS[0]

        if st.button("Refresh data", key="refresh_data", width="stretch"):
            st.cache_data.clear()
            st.rerun()

        st.divider()
        admin_payload = load_admin_data()
        df_admin, households, _ = admin_payload
        start_background_geocoding(df_admin)
        mapped_geo, total_geo = geocode_progress(df_admin)
        if total_geo and mapped_geo < total_geo:
            st.caption(f"Mapping addresses: {mapped_geo}/{total_geo}…")
        col1, col2 = st.columns(2)
        col1.metric("People", len(df_admin))
        col2.metric("Churches", df_admin["Church_Affiliation"].nunique())
        col3, col4 = st.columns(2)
        col3.metric("Households", len(households))
        col4.metric("Members", int(df_admin["Is_Member"].sum()))
        render_staff_sidebar_welcome()

    df, households, events = admin_payload
    render_admin_page(page, df, households, events)


if __name__ == "__main__":
    main()
