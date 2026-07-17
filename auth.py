"""Authentication for the Church Directory admin area (email + password + OTP)."""

from __future__ import annotations

import hashlib
import os
import secrets
import smtplib
import time
import tomllib
from email.message import EmailMessage
from pathlib import Path

import streamlit as st

DATA_DIR = Path(__file__).parent
CREDENTIALS_PATH = DATA_DIR / "admin_credentials.toml"
SAMPLE_CREDENTIALS_PATH = DATA_DIR / "admin_credentials.sample.toml"

SMTP_USER = "dvjgenis@gmail.com"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

OTP_TTL_SECONDS = 600
OTP_RESEND_COOLDOWN_SECONDS = 30

ADMIN_PAGES = [
    ("Directory", "👥 Directory"),
    ("Household Map", "🗺️ Household Map"),
    ("Full Calendar", "📅 Full Calendar"),
    ("Insights", "📊 Insights"),
]

ADMIN_PAGE_LABELS = [label for _, label in ADMIN_PAGES]

SESSION_AUTH_KEY = "auth_authenticated"
SESSION_AUTH_EMAIL_KEY = "auth_email"
SESSION_OTP_EMAIL_KEY = "otp_pending_email"
SESSION_OTP_HASH_KEY = "otp_code_hash"
SESSION_OTP_EXPIRES_KEY = "otp_expires_at"
SESSION_OTP_LAST_SEND_KEY = "otp_last_send_at"
SESSION_DEV_OTP_KEY = "otp_dev_plaintext"


def _is_streamlit_cloud() -> bool:
    return os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud"


def _deep_plain(value):
    if isinstance(value, dict):
        return {str(k): _deep_plain(v) for k, v in value.items()}
    if hasattr(value, "items") and not isinstance(value, (str, bytes)):
        try:
            return {str(k): _deep_plain(v) for k, v in value.items()}
        except Exception:
            return value
    return value


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _emails_from_user_block(user: dict) -> list[str]:
    emails: list[str] = []
    for key in ("email", "email1", "email2", "email3"):
        raw = user.get(key)
        if raw:
            emails.append(_normalize_email(str(raw)))
    return [e for e in emails if e and "@" in e]


def _app_password_from_toml(config: dict) -> str:
    legacy = config.get("Gmail App Password")
    if isinstance(legacy, dict) and legacy.get("app_password"):
        return str(legacy["app_password"]).replace(" ", "")
    for section_key in ("smtp", "gmail_app_password"):
        section = config.get(section_key)
        if isinstance(section, dict) and section.get("app_password"):
            return str(section["app_password"]).replace(" ", "")
    if config.get("app_password"):
        return str(config["app_password"]).replace(" ", "")
    return ""


def _auth_from_toml(config: dict) -> dict | None:
    emails: list[str] = []
    password = ""

    auth_section = config.get("auth")
    if isinstance(auth_section, dict):
        for key in ("email1", "email2", "email3", "email"):
            if auth_section.get(key):
                emails.append(_normalize_email(str(auth_section[key])))
        password = str(auth_section.get("password") or "")

    credentials = config.get("credentials") or {}
    usernames = credentials.get("usernames") or {}
    for user in usernames.values():
        if not isinstance(user, dict):
            continue
        emails.extend(_emails_from_user_block(user))
        if not password and user.get("password"):
            password = str(user["password"])

    emails = list(dict.fromkeys(e for e in emails if e))
    app_password = _app_password_from_toml(config)

    smtp_section = config.get("smtp") or {}
    smtp_user = str(smtp_section.get("user") or SMTP_USER)

    if not emails or not password:
        return None

    return {
        "emails": emails,
        "password": password,
        "smtp_user": smtp_user,
        "smtp_app_password": app_password,
    }


def _auth_from_secrets() -> dict | None:
    try:
        auth_section = st.secrets.get("auth")
        smtp_section = st.secrets.get("smtp")
        if not auth_section:
            return None
        plain_auth = _deep_plain(auth_section)
        plain_smtp = _deep_plain(smtp_section) if smtp_section else {}

        emails: list[str] = []
        for key in ("email1", "email2", "email3", "email"):
            if plain_auth.get(key):
                emails.append(_normalize_email(str(plain_auth[key])))
        if plain_auth.get("emails"):
            for item in plain_auth["emails"]:
                emails.append(_normalize_email(str(item)))

        password = str(plain_auth.get("password") or "")
        emails = list(dict.fromkeys(e for e in emails if e))
        if not emails or not password:
            return None

        app_password = str(plain_smtp.get("app_password") or "").replace(" ", "")
        smtp_user = str(plain_smtp.get("user") or SMTP_USER)

        return {
            "emails": emails,
            "password": password,
            "smtp_user": smtp_user,
            "smtp_app_password": app_password,
        }
    except Exception:
        return None


def _resolve_credentials_path() -> Path | None:
    if CREDENTIALS_PATH.exists():
        return CREDENTIALS_PATH
    if _auth_from_secrets() is not None:
        return None
    if not _is_streamlit_cloud() and SAMPLE_CREDENTIALS_PATH.exists():
        return SAMPLE_CREDENTIALS_PATH
    return None


def credentials_missing() -> bool:
    try:
        load_auth_config()
        return False
    except FileNotFoundError:
        return True


def _load_toml_config(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _load_credentials_file(path: Path) -> dict:
    """Load admin credentials TOML; tolerate legacy [Gmail App Password] table names."""
    try:
        return _load_toml_config(path)
    except tomllib.TOMLDecodeError:
        text = path.read_text(encoding="utf-8")
        fixed = text.replace("[Gmail App Password]", "[gmail_app_password]")
        return tomllib.loads(fixed)


def load_auth_config() -> dict:
    """Return emails, shared password, and SMTP settings."""
    secrets_config = _auth_from_secrets()
    if secrets_config is not None:
        return secrets_config

    path = _resolve_credentials_path()
    if path is None:
        raise FileNotFoundError(
            "No admin credentials found. Copy admin_credentials.sample.toml to "
            "admin_credentials.toml or add [auth] and [smtp] to Streamlit secrets."
        )
    config = _load_credentials_file(path)
    parsed = _auth_from_toml(config)
    if parsed is None:
        raise FileNotFoundError(
            "admin_credentials.toml is missing allowlisted emails or shared password."
        )
    return parsed


def allowed_emails(config: dict | None = None) -> set[str]:
    cfg = config or load_auth_config()
    return set(cfg["emails"])


def verify_password(email: str, password: str, config: dict | None = None) -> bool:
    cfg = config or load_auth_config()
    normalized = _normalize_email(email)
    if normalized not in cfg["emails"]:
        return False
    return password == cfg["password"]


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def store_otp_in_session(email: str, code: str) -> None:
    st.session_state[SESSION_OTP_EMAIL_KEY] = _normalize_email(email)
    st.session_state[SESSION_OTP_HASH_KEY] = _hash_otp(code)
    st.session_state[SESSION_OTP_EXPIRES_KEY] = time.time() + OTP_TTL_SECONDS
    st.session_state.pop(SESSION_DEV_OTP_KEY, None)


def verify_otp(email: str, code: str) -> bool:
    pending_email = st.session_state.get(SESSION_OTP_EMAIL_KEY)
    if not pending_email or _normalize_email(email) != pending_email:
        return False
    expires = st.session_state.get(SESSION_OTP_EXPIRES_KEY, 0)
    if time.time() > expires:
        return False
    expected = st.session_state.get(SESSION_OTP_HASH_KEY)
    if not expected:
        return False
    return _hash_otp(code.strip()) == expected


def _can_resend_otp() -> bool:
    last = st.session_state.get(SESSION_OTP_LAST_SEND_KEY, 0)
    return time.time() - last >= OTP_RESEND_COOLDOWN_SECONDS


def smtp_configured(config: dict) -> bool:
    return bool(config.get("smtp_app_password") and config.get("smtp_user"))


def send_otp_email(to_email: str, code: str, config: dict | None = None) -> None:
    cfg = config or load_auth_config()
    if not smtp_configured(cfg):
        raise RuntimeError("SMTP is not configured (missing app password).")

    msg = EmailMessage()
    msg["Subject"] = "Church Directory — verification code"
    msg["From"] = f"Church Directory <{cfg['smtp_user']}>"
    msg["To"] = to_email
    msg.set_content(
        f"Your verification code is: {code}\n\n"
        f"This code expires in {OTP_TTL_SECONDS // 60} minutes.\n"
        "If you did not request this, you can ignore this email."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(cfg["smtp_user"], cfg["smtp_app_password"])
        server.send_message(msg)


def is_authenticated() -> bool:
    return st.session_state.get(SESSION_AUTH_KEY) is True


def is_admin_authenticated() -> bool:
    """Alias for compatibility with existing call sites."""
    return is_authenticated()


def logout() -> None:
    for key in (
        SESSION_AUTH_KEY,
        SESSION_AUTH_EMAIL_KEY,
        SESSION_OTP_EMAIL_KEY,
        SESSION_OTP_HASH_KEY,
        SESSION_OTP_EXPIRES_KEY,
        SESSION_OTP_LAST_SEND_KEY,
        SESSION_DEV_OTP_KEY,
    ):
        st.session_state.pop(key, None)


def render_credentials_setup_banner() -> None:
    if not credentials_missing():
        return
    st.error(
        "**Login is not configured.** Add `admin_credentials.toml` locally or "
        "`[auth]` and `[smtp]` in Streamlit secrets (see admin_credentials.sample.toml)."
    )


def render_login_page() -> None:
    try:
        config = load_auth_config()
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

    st.markdown("## Church Directory")
    st.caption("Filam & Pillar — authorized staff only")

    pending_email = st.session_state.get(SESSION_OTP_EMAIL_KEY)
    step_two = pending_email is not None

    if not step_two:
        with st.form("login_step1", clear_on_submit=False):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Send verification code", width="stretch")
            if submitted:
                normalized_email = _normalize_email(email)
                if not normalized_email:
                    st.error("Enter your email.")
                elif not verify_password(normalized_email, password, config):
                    st.error("Invalid email or password.")
                elif not _can_resend_otp():
                    st.warning("Please wait 30 seconds before requesting another code.")
                else:
                    code = generate_otp()
                    store_otp_in_session(normalized_email, code)
                    st.session_state[SESSION_OTP_LAST_SEND_KEY] = time.time()
                    try:
                        if smtp_configured(config):
                            send_otp_email(normalized_email, code, config)
                        elif not _is_streamlit_cloud():
                            st.session_state[SESSION_DEV_OTP_KEY] = code
                        else:
                            st.error(
                                "Email is not configured for this deployment. "
                                "Add [smtp] app_password to Streamlit secrets."
                            )
                            st.session_state.pop(SESSION_OTP_EMAIL_KEY, None)
                            st.session_state.pop(SESSION_OTP_HASH_KEY, None)
                            return
                    except Exception as exc:
                        detail = str(exc).strip() or exc.__class__.__name__
                        st.error(f"Could not send verification email: {detail}")
                        st.session_state.pop(SESSION_OTP_EMAIL_KEY, None)
                        st.session_state.pop(SESSION_OTP_HASH_KEY, None)
                        return
                    st.rerun()
        return

    st.info(f"Enter the 6-digit code sent to **{pending_email}**.")
    dev_code = st.session_state.get(SESSION_DEV_OTP_KEY)
    if dev_code and not _is_streamlit_cloud():
        st.warning(f"Local dev: your code is **{dev_code}** (SMTP not configured).")

    with st.form("login_step2", clear_on_submit=False):
        code = st.text_input("Verification code", max_chars=6)
        col_verify, col_back = st.columns(2)
        with col_verify:
            verify = st.form_submit_button("Verify and sign in", width="stretch")
        with col_back:
            back = st.form_submit_button("Use different email", width="stretch")

        if back:
            st.session_state.pop(SESSION_OTP_EMAIL_KEY, None)
            st.session_state.pop(SESSION_OTP_HASH_KEY, None)
            st.session_state.pop(SESSION_OTP_EXPIRES_KEY, None)
            st.session_state.pop(SESSION_DEV_OTP_KEY, None)
            st.rerun()

        if verify:
            if verify_otp(pending_email, code):
                logout_otp_keys_only()
                st.session_state[SESSION_AUTH_KEY] = True
                st.session_state[SESSION_AUTH_EMAIL_KEY] = pending_email
                st.rerun()
            else:
                st.error("Invalid or expired code. Try again or request a new code.")

    if _can_resend_otp():
        if st.button("Resend code", key="resend_otp"):
            code = generate_otp()
            store_otp_in_session(pending_email, code)
            st.session_state[SESSION_OTP_LAST_SEND_KEY] = time.time()
            try:
                if smtp_configured(config):
                    send_otp_email(pending_email, code, config)
                elif not _is_streamlit_cloud():
                    st.session_state[SESSION_DEV_OTP_KEY] = code
                st.success("A new code was sent.")
                st.rerun()
            except Exception as exc:
                detail = str(exc).strip() or exc.__class__.__name__
                st.error(f"Could not resend code: {detail}")
    else:
        st.caption("You can resend a code in about 30 seconds.")


def logout_otp_keys_only() -> None:
    for key in (
        SESSION_OTP_EMAIL_KEY,
        SESSION_OTP_HASH_KEY,
        SESSION_OTP_EXPIRES_KEY,
        SESSION_OTP_LAST_SEND_KEY,
        SESSION_DEV_OTP_KEY,
    ):
        st.session_state.pop(key, None)


def render_sidebar_logout() -> None:
    email = st.session_state.get(SESSION_AUTH_EMAIL_KEY, "Staff")
    st.success(f"Signed in as {email}")
    if st.button("Log out", key="admin_logout", width="stretch"):
        logout()
        st.rerun()


def page_label(section: str) -> str:
    mapping = {section: label for section, label in ADMIN_PAGES}
    return mapping.get(section, section)


def is_admin_page(page: str) -> bool:
    return page in ADMIN_PAGE_LABELS
