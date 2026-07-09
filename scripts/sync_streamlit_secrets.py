#!/usr/bin/env python3
"""Build .streamlit/secrets.toml from the service account JSON key file."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
STREAMLIT_DIR = ROOT / ".streamlit"
DEFAULT_KEY = STREAMLIT_DIR / "filampillardirectory-cb6db0de17be.json"
SECRETS_OUT = STREAMLIT_DIR / "secrets.toml"
ADMIN_CREDS = ROOT / "admin_credentials.toml"
GEOCODE_CACHE = ROOT / "geocode_cache.json"

SHEET_ID = "1n8RTS7LudL23fG9zpc43sPN-IY1WxQt0RZCesTV5iqs"


def _cookie_key() -> str:
    if ADMIN_CREDS.exists():
        with open(ADMIN_CREDS, "rb") as f:
            config = tomllib.load(f)
        return config["cookie"]["key"]
    return "church_directory_auth_key_change_in_production"


def _toml_value(value: str) -> str:
    return json.dumps(value)


def _geocode_cache_section() -> list[str]:
    if not GEOCODE_CACHE.exists():
        return [
            "",
            "# Geocode cache: run `make pregeocode` then `make sync-secrets` to embed map coordinates.",
        ]
    from helpers import is_map_display_coordinate

    cache = json.loads(GEOCODE_CACHE.read_text(encoding="utf-8"))
    mapped = {}
    for address, geo in cache.items():
        lat, lng = geo.get("lat"), geo.get("lng")
        if lat is None or lng is None:
            continue
        try:
            lat_f, lng_f = float(lat), float(lng)
        except (TypeError, ValueError):
            continue
        if not is_map_display_coordinate(lat_f, lng_f):
            continue
        mapped[address] = {"lat": lat_f, "lng": lng_f}
    if not mapped:
        return ["", "# Geocode cache file exists but has no mapped addresses yet."]
    lines = [
        "",
        "# Geocode cache — required on Streamlit Cloud so maps load without live geocoding.",
        "[geocode_cache]",
    ]
    for address, geo in sorted(mapped.items()):
        lines.append(
            f"{_toml_value(address)} = {{ lat = {geo['lat']}, lng = {geo['lng']} }}"
        )
    return lines


def _admin_credentials_section() -> list[str]:
    if not ADMIN_CREDS.exists():
        return []
    with open(ADMIN_CREDS, "rb") as f:
        admin = tomllib.load(f)
    lines = ["", "# Staff login (bcrypt hash — paste into Streamlit Cloud secrets too)"]
    for username, user in admin.get("credentials", {}).get("usernames", {}).items():
        lines.append("")
        lines.append(f"[credentials.usernames.{username}]")
        lines.append(f"email = {_toml_value(str(user.get('email', '')))}")
        lines.append(f"name = {_toml_value(str(user.get('name', '')))}")
        lines.append(f"password = {_toml_value(str(user.get('password', '')))}")
    return lines


def build_secrets_toml(key_path: Path, sheet_id: str) -> str:
    sa = json.loads(key_path.read_text(encoding="utf-8"))
    required = (
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_x509_cert_url",
    )
    missing = [field for field in required if not sa.get(field)]
    if missing:
        raise ValueError(f"Service account JSON missing fields: {', '.join(missing)}")

    lines = [
        "# Generated from the service account JSON — gitignored. Do not commit.",
        f"# Source: {key_path.name}",
        "",
        "[google_sheets]",
        f"sheet_id = {_toml_value(sheet_id)}",
        "",
        "[gcp_service_account]",
    ]
    for field in required:
        lines.append(f"{field} = {_toml_value(str(sa[field]))}")

    lines.extend(_admin_credentials_section())

    cookie_name = "church_directory_cookie"
    cookie_expiry = 1
    if ADMIN_CREDS.exists():
        with open(ADMIN_CREDS, "rb") as f:
            admin = tomllib.load(f)
        cookie_name = str(admin.get("cookie", {}).get("name", cookie_name))
        cookie_expiry = int(admin.get("cookie", {}).get("expiry_days", cookie_expiry))

    lines.extend(
        [
            "",
            "[cookie]",
            f"expiry_days = {cookie_expiry}",
            f"key = {_toml_value(_cookie_key())}",
            f"name = {_toml_value(cookie_name)}",
        ]
    )
    lines.extend(_geocode_cache_section())
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    key_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_KEY
    if not key_path.exists():
        print(f"Service account key not found: {key_path}", file=sys.stderr)
        return 1

    SECRETS_OUT.write_text(build_secrets_toml(key_path, SHEET_ID), encoding="utf-8")
    sa = json.loads(key_path.read_text(encoding="utf-8"))
    print(f"Wrote {SECRETS_OUT}")
    print(f"Service account: {sa['client_email']}")
    print("Share your Google Sheet with that email (Viewer) if you have not already.")
    print("Paste the same contents into Streamlit Cloud → App settings → Secrets.")
    if GEOCODE_CACHE.exists():
        print("Includes [geocode_cache] — maps work immediately after saving secrets and rebooting.")
    else:
        print("Run `make pregeocode` then `make sync-secrets` to add [geocode_cache] for Cloud maps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
