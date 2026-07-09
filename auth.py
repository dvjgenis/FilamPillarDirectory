"""Authentication for the Church Directory staff/admin area."""

from __future__ import annotations

import tomllib
from pathlib import Path

import streamlit as st
import streamlit_authenticator as stauth

DATA_DIR = Path(__file__).parent
CREDENTIALS_PATH = DATA_DIR / "admin_credentials.toml"
SAMPLE_CREDENTIALS_PATH = DATA_DIR / "admin_credentials.sample.toml"

PLACEHOLDER_COOKIE_KEY = "church_directory_auth_key_change_in_production"

PUBLIC_PAGES = [
    ("Overview", "📊 Overview"),
    ("Celebrations", "📅 Celebrations"),
    ("Map", "🗺️ Map"),
    ("Name Lookup", "🔍 Name Lookup"),
]

ADMIN_PAGES = [
    ("Directory", "👥 Directory"),
    ("Household Map", "🗺️ Household Map"),
    ("Full Calendar", "📅 Full Calendar"),
    ("Insights", "📊 Insights"),
]

PUBLIC_PAGE_LABELS = [label for _, label in PUBLIC_PAGES]
ADMIN_PAGE_LABELS = [label for _, label in ADMIN_PAGES]


def _resolve_credentials_path() -> Path | None:
    if CREDENTIALS_PATH.exists():
        return CREDENTIALS_PATH
    if SAMPLE_CREDENTIALS_PATH.exists():
        return SAMPLE_CREDENTIALS_PATH
    return None


def credentials_missing() -> bool:
    try:
        if st.secrets.get("credentials"):
            return False
    except Exception:
        pass
    return not CREDENTIALS_PATH.exists()


def _deep_plain(value):
    """Recursively convert Streamlit AttrDict / Mapping to plain mutable dicts."""
    if isinstance(value, dict):
        return {str(k): _deep_plain(v) for k, v in value.items()}
    if hasattr(value, "items") and not isinstance(value, (str, bytes)):
        try:
            return {str(k): _deep_plain(v) for k, v in value.items()}
        except Exception:
            return value
    return value


def _normalize_cookie(cookie: dict) -> dict:
    """Ensure cookie has the fields streamlit-authenticator requires."""
    return {
        "expiry_days": int(cookie.get("expiry_days", 1)),
        "key": str(cookie.get("key", PLACEHOLDER_COOKIE_KEY)),
        "name": str(cookie.get("name", "church_directory_cookie")),
    }


def _normalize_credentials(credentials: dict) -> dict:
    """
    streamlit-authenticator lowercases usernames and mutates user dicts
    (failed_login_attempts). Secrets AttrDicts are immutable, so convert
    to plain dicts and store usernames in lowercase.
    """
    plain = _deep_plain(credentials)
    usernames = plain.get("usernames") or {}
    plain["usernames"] = {
        str(username).lower(): dict(user) for username, user in usernames.items()
    }
    return plain


def _config_from_secrets() -> dict | None:
    try:
        credentials = st.secrets.get("credentials")
        cookie = st.secrets.get("cookie")
        # Staff login on Streamlit Cloud requires the credentials block.
        if credentials and cookie and cookie.get("key"):
            return {
                "credentials": _normalize_credentials(credentials),
                "cookie": _normalize_cookie(_deep_plain(cookie)),
            }
    except Exception:
        pass
    return None


def load_auth_config() -> dict:
    secrets_config = _config_from_secrets()
    if secrets_config is not None:
        return secrets_config

    path = _resolve_credentials_path()
    if path is None:
        raise FileNotFoundError(
            "No admin credentials found. Run: python scripts/setup_admin.py"
        )
    with open(path, "rb") as f:
        config = tomllib.load(f)
    return {
        "credentials": _normalize_credentials(config.get("credentials", {})),
        "cookie": _normalize_cookie(dict(config.get("cookie", {}))),
    }


def load_authenticator() -> stauth.Authenticate | None:
    """Load credentials from Streamlit secrets or TOML file."""
    try:
        config = load_auth_config()
    except FileNotFoundError:
        return None

    cookie = config["cookie"]
    return stauth.Authenticate(
        config["credentials"],
        cookie["name"],
        cookie["key"],
        cookie["expiry_days"],
        auto_hash=False,
    )


def cookie_key_is_placeholder() -> bool:
    try:
        config = load_auth_config()
    except FileNotFoundError:
        return False
    key = config["cookie"]["key"]
    try:
        key = st.secrets["cookie"]["key"]
    except (KeyError, FileNotFoundError, AttributeError):
        pass
    return key == PLACEHOLDER_COOKIE_KEY


def render_credentials_setup_banner() -> None:
    """Show first-run instructions when admin_credentials.toml is missing."""
    if not credentials_missing():
        return
    st.warning(
        "**Staff login not configured.** Copy `admin_credentials.sample.toml` to "
        "`admin_credentials.toml`, or run `python scripts/setup_admin.py` to generate "
        "secure credentials. Public pages still work without staff login."
    )


def render_security_warnings() -> None:
    if cookie_key_is_placeholder():
        st.warning(
            "Admin cookie signing key is still the default placeholder. "
            "Run `python scripts/setup_admin.py` before deploying publicly."
        )


def is_admin_authenticated() -> bool:
    return st.session_state.get("authentication_status") is True


def render_sidebar_auth(authenticator: stauth.Authenticate | None) -> bool:
    """Render staff login/logout in the sidebar. Returns True if authenticated."""
    if authenticator is None:
        st.markdown("**Staff Login**")
        st.caption("Configure `admin_credentials.toml` to enable staff access.")
        return False

    if is_admin_authenticated():
        name = st.session_state.get("name", "Staff")
        st.success(f"Signed in as {name}")
        authenticator.logout(location="sidebar", key="admin_logout")
        return True

    st.markdown("**Staff Login**")
    st.caption("Authorized staff only — sign in for the full directory.")
    authenticator.login(location="sidebar", key="admin_login")

    if st.session_state.get("authentication_status") is False:
        st.error("Invalid username or password.")

    return False


def navigation_options() -> list[str]:
    """Return exactly 4 pages — admin set when signed in, public set otherwise."""
    if is_admin_authenticated():
        return ADMIN_PAGE_LABELS
    return PUBLIC_PAGE_LABELS


def page_label(section: str) -> str:
    """Map internal section id to display label."""
    mapping = {section: label for section, label in PUBLIC_PAGES + ADMIN_PAGES}
    return mapping.get(section, section)


def is_admin_page(page: str) -> bool:
    return page in ADMIN_PAGE_LABELS
