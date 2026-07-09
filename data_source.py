"""Load church directory data from CSV or Google Sheets."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from helpers import CSV_COLUMNS, CSV_DTYPES, SAMPLE_CSV_PATH

DATA_DIR = Path(__file__).parent

_GSPREAD_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Share the directory sheet with this email (Viewer) for Streamlit Cloud deployment.
PROJECT_SERVICE_ACCOUNT_EMAIL = (
    "filampillardirectory-sa@filampillardirectory.iam.gserviceaccount.com"
)

DEFAULT_SERVICE_ACCOUNT_KEY = (
    DATA_DIR / ".streamlit" / "filampillardirectory-cb6db0de17be.json"
)


def _data_source_env() -> str:
    return os.environ.get("CHURCH_DATA_SOURCE", "").strip().lower()


def uses_google_sheets() -> bool:
    """True when configured to load directory data from Google Sheets."""
    source = _data_source_env()
    if source == "csv":
        return False
    if source == "sheets":
        return True
    return bool(sheet_id())


def sheet_id() -> str | None:
    env_id = os.environ.get("CHURCH_SHEET_ID", "").strip()
    if env_id:
        return env_id
    try:
        import streamlit as st

        secrets = st.secrets.get("google_sheets", {})
        sid = secrets.get("sheet_id", "")
        return str(sid).strip() or None
    except Exception:
        return None


def worksheet_name() -> str | None:
    env_name = os.environ.get("CHURCH_SHEET_WORKSHEET", "").strip()
    if env_name:
        return env_name
    try:
        import streamlit as st

        secrets = st.secrets.get("google_sheets", {})
        name = secrets.get("worksheet", "")
        return str(name).strip() or None
    except Exception:
        return None


def sheet_cache_ttl() -> int:
    return int(os.environ.get("CHURCH_SHEET_CACHE_TTL", "300"))


def _service_account_info() -> dict | None:
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if creds_path and Path(creds_path).exists():
        return json.loads(Path(creds_path).read_text(encoding="utf-8"))

    inline = os.environ.get("CHURCH_GCP_SERVICE_ACCOUNT_JSON", "").strip()
    if inline:
        return json.loads(inline)

    try:
        import streamlit as st

        info = st.secrets.get("gcp_service_account")
        if info:
            return dict(info)
    except Exception:
        pass

    if DEFAULT_SERVICE_ACCOUNT_KEY.exists():
        sa_info = _load_service_account_json(DEFAULT_SERVICE_ACCOUNT_KEY)
        if sa_info:
            return sa_info

    return None


def _scope_error_message() -> str:
    return (
        "Google Sheets access denied.\n\n"
        "Check that the sheet is shared with:\n"
        f"  {PROJECT_SERVICE_ACCOUNT_EMAIL} (Viewer)\n\n"
        "Local dev: ensure .streamlit/filampillardirectory-cb6db0de17be.json exists "
        "and run `make sync-secrets`.\n"
        "Streamlit Cloud: paste .streamlit/secrets.toml into App settings → Secrets."
    )


def format_sheets_load_error(exc: BaseException) -> str | None:
    """Return a user-facing message for common Google Sheets auth failures."""
    import gspread

    cause = exc.__cause__
    if cause is not None:
        nested = format_sheets_load_error(cause)
        if nested:
            return nested

    if isinstance(exc, gspread.exceptions.APIError):
        text = str(exc)
        if "insufficient authentication scopes" in text.lower():
            return _scope_error_message()
        if exc.response.status_code == 403:
            if "has not been used" in text.lower() or "is disabled" in text.lower():
                return (
                    "Google Sheets API is not enabled on your GCP project "
                    "'filampillardirectory'.\n\n"
                    "Enable these APIs (select project filampillardirectory first):\n"
                    "• https://console.cloud.google.com/apis/library/sheets.googleapis.com?project=filampillardirectory\n"
                    "• https://console.cloud.google.com/apis/library/drive.googleapis.com?project=filampillardirectory\n\n"
                    "Wait 1–2 minutes, then restart the app.\n"
                    f"Sheet sharing with {PROJECT_SERVICE_ACCOUNT_EMAIL} (Viewer) looks correct."
                )
            return (
                f"Google Sheets access denied: {text}\n\n"
                "Enable the Google Sheets API on project 'filampillardirectory' and confirm "
                f"the sheet is shared with {PROJECT_SERVICE_ACCOUNT_EMAIL} (Viewer)."
            )
        if exc.response.status_code == 404:
            return (
                "Google Sheet not found. Check `google_sheets.sheet_id` in "
                ".streamlit/secrets.toml."
            )

    if isinstance(exc, PermissionError):
        return _scope_error_message()

    return None


def _open_spreadsheet(client, sheet_id: str):
    import gspread

    try:
        return client.open_by_key(sheet_id)
    except PermissionError as exc:
        raise PermissionError(format_sheets_load_error(exc) or str(exc)) from exc
    except gspread.exceptions.APIError as exc:
        message = format_sheets_load_error(exc)
        if message:
            raise RuntimeError(message) from exc
        raise


def _load_service_account_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("type") == "service_account":
        return data
    return None


def _get_gspread_client():
    import gspread

    info = _service_account_info()
    if info and info.get("type") == "service_account":
        return gspread.service_account_from_dict(info, scopes=_GSPREAD_SCOPES)

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if creds_path:
        sa_info = _load_service_account_json(Path(creds_path))
        if sa_info:
            return gspread.service_account(filename=creds_path, scopes=_GSPREAD_SCOPES)

    raise FileNotFoundError(
        "Google Sheets is enabled but no service account credentials were found.\n"
        "Local dev: place the JSON key at .streamlit/filampillardirectory-cb6db0de17be.json "
        "and run `make sync-secrets`.\n"
        "Streamlit Cloud: paste .streamlit/secrets.toml into App settings → Secrets.\n"
        f"Share the sheet with {PROJECT_SERVICE_ACCOUNT_EMAIL} (Viewer)."
    )


def load_directory_from_sheets() -> pd.DataFrame:
    """Fetch the directory worksheet as a DataFrame."""
    sid = sheet_id()
    if not sid:
        raise ValueError(
            "CHURCH_DATA_SOURCE=sheets but no sheet id configured. "
            "Set CHURCH_SHEET_ID or google_sheets.sheet_id in secrets."
        )

    import gspread

    client = _get_gspread_client()
    spreadsheet = _open_spreadsheet(client, sid)
    ws_name = worksheet_name()
    worksheet = spreadsheet.worksheet(ws_name) if ws_name else spreadsheet.sheet1

    records = worksheet.get_all_records()
    if not records:
        ws_label = ws_name or "(first worksheet)"
        raise RuntimeError(
            f"Google Sheet '{sid}' worksheet '{ws_label}' returned no rows. "
            "Check that the service account has Viewer access and the worksheet tab name is correct."
        )

    df = pd.DataFrame(records)
    for col in CSV_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[CSV_COLUMNS]

    for col in CSV_DTYPES:
        if col in df.columns:
            df[col] = df[col].astype(str).replace({"nan": "", "None": ""})

    return df


def load_directory_from_csv() -> pd.DataFrame:
    from helpers import CSV_PATH

    if not CSV_PATH.exists():
        hint = (
            f"Place your directory CSV at {CSV_PATH.name}, set CHURCH_CSV_PATH, "
            f"or use data/sample_directory.csv for local dev. "
            f"Sample path: {SAMPLE_CSV_PATH.relative_to(DATA_DIR)}."
        )
        raise FileNotFoundError(f"Directory CSV not found: {CSV_PATH}\n{hint}")
    return pd.read_csv(CSV_PATH, dtype=CSV_DTYPES)


def load_raw_directory() -> pd.DataFrame:
    """Load directory rows from Google Sheets or local CSV."""
    if uses_google_sheets():
        return load_directory_from_sheets()
    return load_directory_from_csv()


def directory_cache_key() -> str:
    """Cache invalidation key — CSV mtime for files, fixed key + TTL for sheets."""
    if uses_google_sheets():
        return f"sheets:{sheet_id()}"
    from helpers import CSV_PATH

    try:
        return f"csv:{CSV_PATH.stat().st_mtime}"
    except OSError:
        return "csv:missing"


def data_source_label() -> str:
    if uses_google_sheets():
        return "Google Sheets"
    from helpers import CSV_PATH

    return f"CSV ({CSV_PATH.name})"
