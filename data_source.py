"""Load church directory data from CSV or Google Sheets."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from helpers import CSV_COLUMNS, CSV_DTYPES, SAMPLE_CSV_PATH

DATA_DIR = Path(__file__).parent.parent


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
    return None


def _get_gspread_client():
    import gspread

    info = _service_account_info()
    if info:
        return gspread.service_account_from_dict(info)

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if creds_path:
        return gspread.service_account(filename=creds_path)

    raise FileNotFoundError(
        "Google Sheets is enabled but no service account credentials were found. "
        "Set gcp_service_account in Streamlit secrets, GOOGLE_APPLICATION_CREDENTIALS, "
        "or CHURCH_GCP_SERVICE_ACCOUNT_JSON."
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
    spreadsheet = client.open_by_key(sid)
    ws_name = worksheet_name()
    worksheet = spreadsheet.worksheet(ws_name) if ws_name else spreadsheet.sheet1

    records = worksheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=CSV_COLUMNS)

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
