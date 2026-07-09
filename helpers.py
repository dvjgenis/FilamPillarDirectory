"""Data loading, geocoding, and helper utilities for the Church Directory app."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import openlocationcode.openlocationcode as olc
import pandas as pd
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim

DATA_DIR = Path(__file__).parent
DEFAULT_CSV_PATH = DATA_DIR / "Filam_Pillar Church Directory - Main.csv"
SAMPLE_CSV_PATH = DATA_DIR / "data" / "sample_directory.csv"
CSV_PATH = Path(os.environ.get("CHURCH_CSV_PATH", DEFAULT_CSV_PATH))
GEOCODE_CACHE_PATH = Path(
    os.environ.get("CHURCH_GEOCODE_CACHE_PATH", DATA_DIR / "geocode_cache.json")
)

CSV_DTYPES = {
    "Phone_Number": str,
    "Spouse_Phone": str,
}

# All 15 columns from Filam_Pillar Church Directory - Main.csv
CSV_COLUMNS = [
    "Church_Affiliation",
    "First_Name",
    "Last_Name",
    "Birthday",
    "Home_Address",
    "Phone_Number",
    "Email_Address",
    "Wedding_Anniversary",
    "Spouse_Name",
    "Spouse_Birthday",
    "Spouse_Phone",
    "Children_Names",
    "Children_Birthdays",
    "Is_Member",
    "Opt_In_Announcements",
]

# Shown on public person-level views only
PUBLIC_PERSON_COLUMNS = [
    "First_Name",
    "Last_Name",
    "Full_Name",
    "Church_Affiliation",
]

# Safe for public aggregate charts (city counts, etc.)
PUBLIC_AGGREGATE_COLUMNS = PUBLIC_PERSON_COLUMNS + ["City"]

PUBLIC_MAP_COLUMNS = ["Church_Affiliation", "Home_Address"]

# Minor/sensitive fields — admin only (includes children)
MINOR_FIELDS = ["Children_Names", "Children_Birthdays"]

SENSITIVE_FIELDS = [
    "Home_Address",
    "Phone_Number",
    "Email_Address",
    "Birthday",
    "Wedding_Anniversary",
    "Spouse_Name",
    "Spouse_Birthday",
    "Spouse_Phone",
    *MINOR_FIELDS,
    "Is_Member",
    "Opt_In_Announcements",
]

ALL_DISPLAY_FIELDS = list(CSV_COLUMNS)

CHURCH_COLORS = {
    "Filam": "#2563EB",
    "Pillar": "#DC2626",
}

CHURCH_MARKER_STYLES = {
    "Filam": {
        "fill": [251, 191, 36, 255],
        "border": [30, 64, 175, 255],
        "label_color": [30, 64, 175, 255],
    },
    "Pillar": {
        "fill": [251, 191, 36, 255],
        "border": [153, 27, 27, 255],
        "label_color": [153, 27, 27, 255],
    },
}

CHURCH_LOCATIONS = {
    "Filam": "5253 W Byron St, Chicago, IL 60641",
    "Pillar": "2012 Wicklow Rd, Naperville, IL 60564",
}

CHURCH_FULL_NAMES = {
    "Filam": "Fil-American Baptist Church",
    "Pillar": "Pillar of Faith Baptist Church",
}

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def church_full_name(church: str) -> str:
    return CHURCH_FULL_NAMES.get(church, church)


def _is_missing(value) -> bool:
    if pd.isna(value):
        return True
    text = str(value).strip()
    return not text or text.lower() in {"nan", "none", "n/a", "na", "<na>", "not available"}


def display_value(value) -> str:
    """Return 'Not available' for NaN/empty; otherwise formatted string."""
    if _is_missing(value):
        return "Not available"
    return str(value).strip()


def format_phone(value) -> str:
    """Format phone numbers; return 'Not available' when missing."""
    if _is_missing(value):
        return "Not available"

    text = str(value).strip()
    if "e+" in text.lower() or (text.replace(".", "", 1).isdigit() and "." in text):
        try:
            text = str(int(float(text)))
        except ValueError:
            pass
    elif text.replace(".", "").isdigit() and "." in text:
        try:
            text = str(int(float(text)))
        except ValueError:
            pass

    digits = re.sub(r"\D", "", text)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return text


def csv_mtime() -> float:
    """Return CSV modification time for cache invalidation, or 0 if missing."""
    try:
        return CSV_PATH.stat().st_mtime
    except OSError:
        return 0.0


def geocode_cache_mtime() -> float:
    """Return geocode cache modification time for cache invalidation."""
    try:
        return GEOCODE_CACHE_PATH.stat().st_mtime
    except OSError:
        return 0.0


def load_and_clean() -> pd.DataFrame:
    """Load directory data and add derived columns."""
    from data_source import load_raw_directory

    df = load_raw_directory()
    return clean_directory(df)


def clean_directory(df: pd.DataFrame) -> pd.DataFrame:
    """Validate, filter, and enrich directory rows."""
    missing_cols = [c for c in CSV_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Directory missing expected columns: {missing_cols}")

    df = df.copy()
    df = df[
        df["First_Name"].notna()
        & (df["First_Name"].astype(str).str.strip() != "")
    ].reset_index(drop=True)

    df["Full_Name"] = df["First_Name"].astype(str).str.strip() + " " + df["Last_Name"].astype(str).str.strip()
    df["Is_Member"] = df["Is_Member"].map(_map_bool)
    df["Opt_In_Announcements"] = df["Opt_In_Announcements"].map(_map_bool)
    df["Birthday_Month"], df["Birthday_Day"] = zip(*df["Birthday"].apply(_parse_mmdd))
    df["Anniversary_Month"], df["Anniversary_Day"] = zip(
        *df["Wedding_Anniversary"].apply(_parse_mmdd)
    )
    df["City"] = df["Home_Address"].apply(_extract_city)
    df["State"] = df["Home_Address"].apply(_extract_state)
    return df


def _map_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text in {"true", "yes", "1", "y"}


def assert_public_safe_columns(df: pd.DataFrame) -> None:
    """Raise if a public view receives sensitive columns."""
    forbidden = set(SENSITIVE_FIELDS) & set(df.columns)
    if forbidden:
        raise ValueError(f"Public view received sensitive columns: {sorted(forbidden)}")


def get_public_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return only columns safe for public person-level display."""
    result = df[PUBLIC_PERSON_COLUMNS].copy()
    assert_public_safe_columns(result)
    return result


def get_public_aggregate_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return columns safe for public aggregate charts (no contact/family details)."""
    result = df[PUBLIC_AGGREGATE_COLUMNS].copy()
    assert_public_safe_columns(result)
    return result


def get_public_map_df(df: pd.DataFrame) -> pd.DataFrame:
    """Minimal columns for public heatmap (addresses never shown in UI)."""
    return df[PUBLIC_MAP_COLUMNS].copy()


PUBLIC_EVENT_FIELDS = {"type", "name", "month", "day", "church"}


def sanitize_events_for_public(events: list[dict]) -> list[dict]:
    """Replace event names with first names only; strip admin-only fields."""
    public = []
    for e in events:
        if e["type"] == "birthday":
            first = e.get("first_name") or (e["name"].split()[0] if e.get("name") else "")
            name = display_value(first) if not _is_missing(first) else "Someone"
        elif e["type"] == "anniversary":
            parts = e["name"].split(" & ")
            first_names = [p.split()[0] for p in parts if p.strip()]
            name = " & ".join(first_names) if first_names else "Anniversary"
        else:
            continue

        public.append({
            "type": e["type"],
            "name": name,
            "month": e["month"],
            "day": e["day"],
            "church": e["church"],
        })
    return public


def _parse_mmdd(value) -> tuple[int | None, int | None]:
    """Parse MM/DD; return (None, None) for missing or invalid values."""
    if pd.isna(value):
        return None, None

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "not available", "n/a", "na"}:
        return None, None

    parts = text.split("/")
    if len(parts) != 2:
        return None, None

    try:
        month, day = int(parts[0]), int(parts[1])
    except ValueError:
        return None, None

    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None, None

    return month, day


def _extract_city(address: str) -> str:
    if _is_missing(address):
        return ""
    parts = [p.strip() for p in str(address).split(",")]
    if len(parts) >= 2:
        return parts[-2]
    return ""


def _extract_state(address: str) -> str:
    if _is_missing(address):
        return ""
    parts = [p.strip() for p in str(address).split(",")]
    if len(parts) >= 1:
        state_zip = parts[-1].split()
        if state_zip:
            return state_zip[0]
    return ""


def group_households(df: pd.DataFrame) -> list[dict]:
    """Group people by home address into household dicts."""
    households = []
    valid_df = df[~df["Home_Address"].apply(_is_missing)]
    for address, group in valid_df.groupby("Home_Address", sort=False):
        members = group.sort_values("Last_Name").to_dict("records")
        churches = group["Church_Affiliation"].unique().tolist()
        households.append({
            "address": address,
            "city": group["City"].iloc[0],
            "state": group["State"].iloc[0],
            "size": len(group),
            "churches": churches,
            "primary_church": group["Church_Affiliation"].mode().iloc[0],
            "members": members,
            "member_names": [m["Full_Name"] for m in members],
        })
    households.sort(key=lambda h: (h["city"], h["address"]))
    return households


def _load_file_geocode_cache() -> dict:
    if not GEOCODE_CACHE_PATH.exists():
        return {}
    try:
        with open(GEOCODE_CACHE_PATH) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def _load_secrets_geocode_cache() -> dict:
    try:
        import streamlit as st

        raw = st.secrets.get("geocode_cache")
        if not raw:
            return {}
        if isinstance(raw, dict):
            return dict(raw)
        return json.loads(str(raw))
    except Exception:
        return {}


def load_geocode_cache(*, warn_on_corrupt: bool = False) -> dict:
    """Load geocode cache from secrets bootstrap, then overlay local file."""
    cache = _load_secrets_geocode_cache()
    if not GEOCODE_CACHE_PATH.exists():
        return cache
    try:
        with open(GEOCODE_CACHE_PATH) as f:
            file_cache = json.load(f)
        cache.update(file_cache)
        return cache
    except json.JSONDecodeError:
        if warn_on_corrupt:
            import streamlit as st

            st.warning(
                "Geocode cache file was corrupt and has been reset. "
                "Re-run geocoding from the Household Map page."
            )
        return cache


def collect_directory_addresses(df: pd.DataFrame | None = None) -> list[str]:
    """Unique church + household addresses used on directory maps."""
    addresses = set(get_church_addresses())
    if df is not None and "Home_Address" in df.columns:
        for address in df["Home_Address"].dropna().unique():
            if display_value(address) != "Not available":
                addresses.add(address)
    return sorted(addresses)


def _save_geocode_cache(cache: dict) -> None:
    with open(GEOCODE_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def geocode_missing_count(df: pd.DataFrame | None) -> tuple[int, int]:
    """Return (mapped_count, total_address_count) for directory map addresses."""
    addresses = collect_directory_addresses(df)
    cache = load_geocode_cache()
    mapped = sum(1 for a in addresses if cache.get(a, {}).get("lat") is not None)
    return mapped, len(addresses)


def ensure_map_geocoded(
    df: pd.DataFrame,
    progress_callback=None,
) -> tuple[bool, str | None]:
    """Geocode missing church + household addresses for map views."""
    try:
        ensure_church_geocoded()
        addresses = collect_directory_addresses(df)
        cache = load_geocode_cache()
        missing = [a for a in addresses if a not in cache or cache[a].get("lat") is None]
        if missing:
            geocode_addresses(missing, progress_callback)
        return True, None
    except Exception as exc:
        return False, str(exc).strip() or exc.__class__.__name__


def ensure_directory_geocoded(df: pd.DataFrame) -> None:
    """Pre-geocode church and household addresses so maps work without manual steps."""
    addresses = collect_directory_addresses(df)
    cache = load_geocode_cache()
    missing = [a for a in addresses if a not in cache or cache[a].get("lat") is None]
    if not missing:
        return
    geocode_addresses(missing)


def ensure_church_geocoded() -> None:
    """Pre-geocode church building addresses only (no directory data required)."""
    cache = load_geocode_cache()
    missing = [
        a for a in get_church_addresses()
        if a not in cache or cache[a].get("lat") is None
    ]
    if not missing:
        return
    geocode_addresses(missing)


def _simplify_address(address: str) -> str:
    """Strip unit/apt numbers for fallback geocoding."""
    simplified = re.sub(
        r",?\s*(#|Unit|Apt|Suite|Ste)\s*[\w-]+", "", address, flags=re.IGNORECASE
    )
    return simplified.strip().rstrip(",")


def _parse_plus_code_address(address: str) -> tuple[str, str] | None:
    """Return (plus_code, locality) when the address starts with a Plus Code."""
    text = address.strip()
    if "+" not in text:
        return None

    code_part, _, locality = text.partition(",")
    code = code_part.strip().upper()
    if not (olc.isFull(code) or olc.isShort(code)):
        return None

    return code, locality.strip()


def _plus_code_center(code: str) -> tuple[float, float]:
    area = olc.decode(code)
    return area.latitudeCenter, area.longitudeCenter


def _plus_code_geocode(geolocator, address: str) -> tuple[float, float] | None:
    """Decode Google Plus Codes, including short codes with a locality suffix."""
    parsed = _parse_plus_code_address(address)
    if not parsed:
        return None

    code, locality = parsed
    if olc.isFull(code):
        return _plus_code_center(code)

    if not locality:
        return None

    reference = geolocator.geocode(locality, timeout=10)
    if not reference:
        return None

    full_code = olc.recoverNearest(code, reference.latitude, reference.longitude)
    return _plus_code_center(full_code)


def _census_geocode(address: str) -> tuple[float, float] | None:
    """Fallback geocoder using the free US Census Bureau service."""
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + urllib.parse.urlencode(
        {"address": address, "benchmark": "Public_AR_Current", "format": "json"}
    )
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        matches = data.get("result", {}).get("addressMatches", [])
        if matches:
            coords = matches[0]["coordinates"]
            return coords["y"], coords["x"]
    except (urllib.error.URLError, ValueError, KeyError, TimeoutError):
        return None
    return None


def _try_geocode(geolocator, address: str) -> tuple[float, float] | None:
    """Try Plus Codes, Nominatim (full then simplified), then US Census geocoder."""
    plus_code = _plus_code_geocode(geolocator, address)
    if plus_code:
        return plus_code

    location = geolocator.geocode(address, timeout=10)
    if location:
        return location.latitude, location.longitude

    simplified = _simplify_address(address)
    if simplified != address:
        time.sleep(1.1)
        location = geolocator.geocode(simplified, timeout=10)
        if location:
            return location.latitude, location.longitude

    census = _census_geocode(address)
    if census:
        return census
    if simplified != address:
        return _census_geocode(simplified)
    return None


def geocode_addresses(
    addresses: list[str],
    progress_callback=None,
) -> tuple[dict, list[str]]:
    """Geocode addresses with local JSON cache. Returns {address: {lat, lng}}."""
    cache = load_geocode_cache()
    geolocator = Nominatim(user_agent="church_directory_streamlit")
    failed = []

    for i, address in enumerate(addresses):
        if address in cache and cache[address].get("lat") is not None:
            if progress_callback:
                progress_callback(i + 1, len(addresses), address, cached=True)
            continue

        if progress_callback:
            progress_callback(i + 1, len(addresses), address, cached=False)

        try:
            coords = _try_geocode(geolocator, address)
            if coords:
                cache[address] = {"lat": coords[0], "lng": coords[1]}
            else:
                cache[address] = {"lat": None, "lng": None, "error": "not found"}
                failed.append(address)
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            cache[address] = {"lat": None, "lng": None, "error": str(e)}
            failed.append(address)

        _save_geocode_cache(cache)
        time.sleep(1.1)

    return cache, failed


def _hex_to_rgba(hex_color: str, alpha: int = 200) -> list[int]:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return [r, g, b, alpha]


# Chicagoland + nearby states; keeps international/outlier geocodes off the map.
MAP_DISPLAY_BOUNDS = {
    "lat_min": 36.0,
    "lat_max": 46.5,
    "lng_min": -96.0,
    "lng_max": -82.0,
}


def is_map_display_coordinate(lat: float, lng: float) -> bool:
    """Return True when coordinates fall in the regional map viewport."""
    return (
        MAP_DISPLAY_BOUNDS["lat_min"] <= lat <= MAP_DISPLAY_BOUNDS["lat_max"]
        and MAP_DISPLAY_BOUNDS["lng_min"] <= lng <= MAP_DISPLAY_BOUNDS["lng_max"]
    )


def out_of_region_geocoded_addresses(
    addresses: list[str],
    geocode_cache: dict,
) -> list[str]:
    """Addresses geocoded successfully but outside the regional map bounds."""
    excluded = []
    for address in addresses:
        geo = geocode_cache.get(address, {})
        lat, lng = geo.get("lat"), geo.get("lng")
        if lat is None or lng is None:
            continue
        if not is_map_display_coordinate(lat, lng):
            excluded.append(address)
    return sorted(excluded)


def build_map_data(households: list[dict], geocode_cache: dict) -> pd.DataFrame:
    """Build dataframe for pydeck map from households + geocode cache."""
    rows = []
    for hh in households:
        geo = geocode_cache.get(hh["address"], {})
        lat, lng = geo.get("lat"), geo.get("lng")
        if lat is None or lng is None:
            continue
        if not is_map_display_coordinate(lat, lng):
            continue
        hex_color = CHURCH_COLORS.get(hh["primary_church"], "#6B7280")
        rows.append({
            "address": hh["address"],
            "lat": lat,
            "lng": lng,
            "church": hh["primary_church"],
            "size": hh["size"],
            "radius_pixels": min(6 + hh["size"] * 3, 24),
            "city": hh["city"],
            "members": ", ".join(hh["member_names"]),
            "color": _hex_to_rgba(hex_color),
        })
    return pd.DataFrame(rows)


def get_church_addresses() -> list[str]:
    return list(CHURCH_LOCATIONS.values())


def build_church_map_data(
    geocode_cache: dict,
    churches: list[str] | None = None,
) -> pd.DataFrame:
    """Build dataframe for church building markers."""
    rows = []
    for church, address in CHURCH_LOCATIONS.items():
        if churches and church not in churches:
            continue
        geo = geocode_cache.get(address, {})
        if geo.get("lat") is None:
            continue
        style = CHURCH_MARKER_STYLES.get(church, CHURCH_MARKER_STYLES["Filam"])
        rows.append({
            "address": address,
            "lat": geo["lat"],
            "lng": geo["lng"],
            "church": church_full_name(church),
            "members": f"⛪ {church_full_name(church)}",
            "label": f"⛪ {church}",
            "fill_color": style["fill"],
            "border_color": style["border"],
            "label_color": style["label_color"],
        })
    return pd.DataFrame(rows)


# ~8–10 mile grid cells — neighborhood-scale, not street-level
PUBLIC_DENSITY_GRID_SIZE = 0.12

# Soft per-cell weight; multiple households in a cell stack gently
PUBLIC_HOUSEHOLD_HEAT_WEIGHT = 0.35


def build_public_density_data(
    df: pd.DataFrame,
    geocode_cache: dict,
    church: str | None = None,
    grid_size: float = PUBLIC_DENSITY_GRID_SIZE,
) -> pd.DataFrame:
    """
    Build privacy-safe heatmap points aggregated to coarse neighborhood cells.
    Households in the same cell share one blob at the cell center — never one pin per home.
    """
    if church and church != "All":
        df = df[df["Church_Affiliation"] == church]

    cell_weights: dict[tuple[float, float], float] = {}
    valid_df = df[~df["Home_Address"].apply(_is_missing)]

    for address, _group in valid_df.groupby("Home_Address", sort=False):
        geo = geocode_cache.get(address, {})
        lat, lng = geo.get("lat"), geo.get("lng")
        if lat is None or lng is None:
            continue
        if not is_map_display_coordinate(lat, lng):
            continue
        snap_lat = round(lat / grid_size) * grid_size
        snap_lng = round(lng / grid_size) * grid_size
        key = (snap_lat, snap_lng)
        cell_weights[key] = cell_weights.get(key, 0.0) + PUBLIC_HOUSEHOLD_HEAT_WEIGHT

    rows = [
        {"lat": lat, "lng": lng, "weight": weight}
        for (lat, lng), weight in cell_weights.items()
    ]
    return pd.DataFrame(rows)


def _has_valid_date(month, day) -> bool:
    if month is None or day is None or pd.isna(month) or pd.isna(day):
        return False
    return True


def _anniversary_couple_names(group: pd.DataFrame, month: int, day: int) -> str:
    """Build a couple display name from household members sharing an anniversary date."""
    couple = group[
        (group["Anniversary_Month"] == month) & (group["Anniversary_Day"] == day)
    ].sort_values("Last_Name")
    if couple.empty:
        return ""

    names = couple["Full_Name"].tolist()
    if len(names) <= 2:
        return " & ".join(names)

    by_last = couple.groupby("Last_Name")["Full_Name"].apply(list).to_dict()
    largest = max(by_last.values(), key=len)
    if len(largest) >= 2:
        return " & ".join(sorted(largest)[:2])
    return " & ".join(names[:2])


def build_events(df: pd.DataFrame) -> list[dict]:
    """Build list of birthday and anniversary events."""
    events = []
    for _, row in df.iterrows():
        if not _has_valid_date(row["Birthday_Month"], row["Birthday_Day"]):
            continue
        events.append({
            "type": "birthday",
            "name": row["Full_Name"],
            "first_name": row["First_Name"],
            "month": int(row["Birthday_Month"]),
            "day": int(row["Birthday_Day"]),
            "date_str": row["Birthday"],
            "church": row["Church_Affiliation"],
            "address": row["Home_Address"],
        })

    seen_anniversaries: set[tuple] = set()
    valid_df = df[~df["Home_Address"].apply(_is_missing)]
    for address, group in valid_df.groupby("Home_Address"):
        anniv_rows = group[
            group["Anniversary_Month"].notna() & group["Anniversary_Day"].notna()
        ]
        if anniv_rows.empty:
            continue

        for (month, day), couple_group in anniv_rows.groupby(["Anniversary_Month", "Anniversary_Day"]):
            month, day = int(month), int(day)
            key = (month, day, address)
            if key in seen_anniversaries:
                continue
            seen_anniversaries.add(key)

            names = _anniversary_couple_names(group, month, day)
            if not names:
                continue

            churches = couple_group["Church_Affiliation"].unique()
            events.append({
                "type": "anniversary",
                "name": names,
                "first_name": None,
                "month": month,
                "day": day,
                "date_str": couple_group["Wedding_Anniversary"].iloc[0],
                "church": churches[0] if len(churches) == 1 else "Both",
                "address": address,
            })

    return events


def _normalize_address(address: str) -> str:
    return str(address).strip().lower()


def _dedupe_admin_events(events: list[dict]) -> list[dict]:
    """Remove exact duplicate calendar rows while keeping distinct event types."""
    seen: set[tuple] = set()
    unique: list[dict] = []
    for e in events:
        key = (
            e.get("type"),
            str(e.get("name", "")).lower().strip(),
            e.get("month"),
            e.get("day"),
            _normalize_address(e.get("address", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    return unique


def _child_has_own_birthday_on_date(
    df: pd.DataFrame, child_name: str, month: int, day: int
) -> bool:
    """True when a directory member already has an adult birthday on this date."""
    child = child_name.lower().strip()
    if not child:
        return False
    child_first = child.split()[0]
    for _, row in df.iterrows():
        if _is_missing(row.get("Birthday_Month")) or _is_missing(row.get("Birthday_Day")):
            continue
        try:
            row_month = int(row["Birthday_Month"])
            row_day = int(row["Birthday_Day"])
        except (TypeError, ValueError):
            continue
        if row_month != month or row_day != day:
            continue
        full = str(row["Full_Name"]).lower().strip()
        first = str(row["First_Name"]).lower().strip()
        if full == child or full.startswith(child + " "):
            return True
        if child in full and first == child_first:
            return True
    return False


def _build_children_birthday_events(df: pd.DataFrame) -> list[dict]:
    """Parse Children_Names + Children_Birthdays into admin-only calendar events."""
    # Merge duplicate entries when both parents list the same child at the same address.
    pending: dict[tuple, dict] = {}

    for _, row in df.iterrows():
        if _is_missing(row.get("Children_Names")) or _is_missing(row.get("Children_Birthdays")):
            continue
        address = row["Home_Address"]
        if _is_missing(address):
            continue
        norm_address = _normalize_address(address)

        names = [n.strip() for n in str(row["Children_Names"]).split(",") if n.strip()]
        bdays = [d.strip() for d in str(row["Children_Birthdays"]).split(",") if d.strip()]

        for i, child_name in enumerate(names):
            if i >= len(bdays):
                break
            month, day = _parse_mmdd(bdays[i])
            if month is None:
                continue
            if _child_has_own_birthday_on_date(df, child_name, int(month), int(day)):
                continue

            key = (norm_address, child_name.lower().strip(), int(month), int(day))
            if key not in pending:
                pending[key] = {
                    "type": "child_birthday",
                    "name": child_name,
                    "first_name": child_name.split()[0],
                    "month": int(month),
                    "day": int(day),
                    "date_str": bdays[i],
                    "church": row["Church_Affiliation"],
                    "address": address,
                    "parents": [row["Full_Name"]],
                }
            elif row["Full_Name"] not in pending[key]["parents"]:
                pending[key]["parents"].append(row["Full_Name"])

    events = []
    for entry in pending.values():
        parents = entry.pop("parents")
        parent_label = " & ".join(parents)
        entry["display_name"] = f"{entry['name']} (child of {parent_label})"
        entry["parent"] = parent_label
        events.append(entry)
    return events


def build_admin_events(df: pd.DataFrame) -> list[dict]:
    """All calendar events for staff — includes children's birthdays from parent records."""
    events = build_events(df)
    events.extend(_build_children_birthday_events(df))
    return _dedupe_admin_events(events)


def is_birthday_event(event: dict) -> bool:
    return event.get("type") in ("birthday", "child_birthday")


def event_icon(event_type: str) -> str:
    if event_type == "birthday":
        return "🎂"
    if event_type == "child_birthday":
        return "👶"
    return "💍"


def get_events_for_month(events: list[dict], month: int) -> list[dict]:
    return [
        e for e in events
        if _has_valid_date(e["month"], e["day"]) and e["month"] == month
    ]


def get_upcoming_events(events: list[dict], from_date: date | None = None, days: int = 30) -> list[dict]:
    """Return events occurring in the next N days (rolling year)."""
    if from_date is None:
        from_date = date.today()

    upcoming = []
    for e in events:
        if not _has_valid_date(e["month"], e["day"]):
            continue
        next_occurrence = _next_occurrence(int(e["month"]), int(e["day"]), from_date)
        delta = (next_occurrence - from_date).days
        if 0 <= delta <= days:
            upcoming.append({**e, "next_date": next_occurrence, "days_away": delta})

    upcoming.sort(key=lambda e: e["days_away"])
    return upcoming


def get_today_events(events: list[dict], today: date | None = None) -> list[dict]:
    if today is None:
        today = date.today()
    return [
        e for e in events
        if _has_valid_date(e["month"], e["day"])
        and int(e["month"]) == today.month
        and int(e["day"]) == today.day
    ]


def _next_occurrence(month: int, day: int, from_date: date) -> date:
    """Get next calendar occurrence of MM/DD from from_date."""
    year = from_date.year
    try:
        candidate = date(year, month, day)
    except ValueError:
        candidate = date(year, month, 28)

    if candidate < from_date:
        try:
            candidate = date(year + 1, month, day)
        except ValueError:
            candidate = date(year + 1, month, 28)
    return candidate


def month_calendar_grid(year: int, month: int) -> list[list[int | None]]:
    """Return weeks as lists of day numbers (None for padding)."""
    first = date(year, month, 1)
    start_weekday = first.weekday()
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    num_days = (next_month - first).days

    days: list[int | None] = [None] * start_weekday
    days.extend(range(1, num_days + 1))

    while len(days) % 7 != 0:
        days.append(None)

    weeks = []
    for i in range(0, len(days), 7):
        weeks.append(days[i : i + 7])
    return weeks


def filter_people(
    df: pd.DataFrame,
    search: str = "",
    churches: list[str] | None = None,
    member_filter: str = "All",
    opt_in_filter: str = "All",
    sort_by: str = "Last Name",
    search_address: bool = True,
) -> pd.DataFrame:
    result = df.copy()

    if search:
        q = search.lower()
        mask = (
            result["Full_Name"].str.lower().str.contains(q, na=False)
            | result["First_Name"].str.lower().str.contains(q, na=False)
            | result["Last_Name"].str.lower().str.contains(q, na=False)
        )
        if search_address and "Home_Address" in result.columns:
            mask = mask | result["Home_Address"].str.lower().str.contains(q, na=False)
        result = result[mask]

    if churches:
        result = result[result["Church_Affiliation"].isin(churches)]

    if "Is_Member" in result.columns:
        if member_filter == "Members":
            result = result[result["Is_Member"]]
        elif member_filter == "Non-Members":
            result = result[~result["Is_Member"]]

    if "Opt_In_Announcements" in result.columns:
        if opt_in_filter == "Opted In":
            result = result[result["Opt_In_Announcements"]]
        elif opt_in_filter == "Not Opted In":
            result = result[~result["Opt_In_Announcements"]]

    sort_cols = {
        "Last Name": ["Last_Name", "First_Name"],
        "First Name": ["First_Name", "Last_Name"],
        "Church": ["Church_Affiliation", "Last_Name", "First_Name"],
    }
    result = result.sort_values(sort_cols.get(sort_by, ["Last_Name", "First_Name"]))
    return result.reset_index(drop=True)


def city_church_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    city_df = df[~df["City"].apply(_is_missing)]
    return (
        city_df.groupby(["City", "Church_Affiliation"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )


def month_event_counts_by_church(events: list[dict], event_type: str) -> pd.DataFrame:
    """Count events per month, split by church affiliation."""
    if event_type == "birthday":
        match_types = ("birthday", "child_birthday")
    else:
        match_types = (event_type,)

    counts = {(m, c): 0 for m in range(1, 13) for c in CHURCH_COLORS}
    for e in events:
        if not isinstance(e, dict) or e.get("type") not in match_types:
            continue
        church = e.get("church")
        month = e.get("month")
        if church in CHURCH_COLORS and isinstance(month, int) and 1 <= month <= 12:
            counts[(month, church)] += 1

    rows = []
    for month in range(1, 13):
        for church in CHURCH_COLORS:
            rows.append({
                "month": month,
                "month_name": MONTH_ABBR[month - 1],
                "church": church,
                "count": counts[(month, church)],
            })
    return pd.DataFrame(rows)


def household_size_counts(households: list[dict]) -> pd.DataFrame:
    """Discrete household size distribution for bar charts."""
    sizes = [h["size"] for h in households]
    if not sizes:
        return pd.DataFrame({"size": [], "count": []})
    max_size = max(sizes)
    counts = {s: 0 for s in range(1, max_size + 1)}
    for s in sizes:
        counts[s] += 1
    return pd.DataFrame({
        "size": list(counts.keys()),
        "count": list(counts.values()),
    })


def is_valid_mmdd(value) -> bool:
    """Return True when a value parses as a valid MM/DD date."""
    month, day = _parse_mmdd(value)
    return month is not None


def audit_data_quality(df: pd.DataFrame) -> dict:
    """Return counts and issue lists for the admin data-quality panel."""
    issues: dict = {
        "missing_birthdays": [],
        "missing_phones": [],
        "missing_emails": [],
        "children_mismatches": [],
        "invalid_birthdays": [],
        "invalid_anniversaries": [],
    }

    for _, row in df.iterrows():
        name = f"{row.get('First_Name', '')} {row.get('Last_Name', '')}".strip()
        if not is_valid_mmdd(row.get("Birthday")):
            if _is_missing(row.get("Birthday")):
                issues["missing_birthdays"].append(name)
            else:
                issues["invalid_birthdays"].append(f"{name}: {row.get('Birthday')}")

        if _is_missing(row.get("Phone_Number")):
            issues["missing_phones"].append(name)
        if _is_missing(row.get("Email_Address")):
            issues["missing_emails"].append(name)

        if not _is_missing(row.get("Wedding_Anniversary")) and not is_valid_mmdd(row.get("Wedding_Anniversary")):
            issues["invalid_anniversaries"].append(f"{name}: {row.get('Wedding_Anniversary')}")

        if _is_missing(row.get("Children_Names")) and _is_missing(row.get("Children_Birthdays")):
            continue
        names = [n.strip() for n in str(row.get("Children_Names", "")).split(",") if n.strip()]
        bdays = [d.strip() for d in str(row.get("Children_Birthdays", "")).split(",") if d.strip()]
        if len(names) != len(bdays):
            issues["children_mismatches"].append(
                f"{name}: {len(names)} name(s) vs {len(bdays)} birthday(s)"
            )

    return issues


def person_key(row: pd.Series | dict) -> str:
    """Stable key for a person row (handles duplicate full names)."""
    if isinstance(row, dict):
        full_name = row.get("Full_Name", "")
        address = row.get("Home_Address", "")
    else:
        full_name = row["Full_Name"]
        address = row.get("Home_Address", "")
    return f"{full_name}|{display_value(address)}"


def style_figure(
    fig,
    *,
    height: int = 380,
    title: str | None = None,
    show_legend: bool = True,
    pie: bool = False,
    theme: str = "light",
):
    """Apply consistent Plotly styling across dashboard charts."""
    if theme == "light":
        template = "plotly_white"
        font_color = "#1F2937"
        paper_bg = "#FFFFFF"
        plot_bg = "#FFFFFF"
        grid_color = "#E5E7EB"
        tick_size = 13
    else:
        template = "plotly_dark"
        font_color = "#F1F5F9"
        paper_bg = "rgba(0,0,0,0)"
        plot_bg = "#1E293B"
        grid_color = "#334155"
        tick_size = 12

    layout = dict(
        template=template,
        height=height,
        paper_bgcolor=paper_bg,
        plot_bgcolor=plot_bg,
        margin=dict(l=40, r=20, t=50 if title else 30, b=40),
        font=dict(family="sans-serif", size=13, color=font_color),
    )
    if show_legend:
        layout["legend"] = dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=font_color),
        )
    else:
        layout["showlegend"] = False

    if title:
        layout["title"] = dict(text=title, x=0, font=dict(size=16, color=font_color))

    fig.update_layout(**layout)
    fig.update_xaxes(
        gridcolor=grid_color,
        zerolinecolor=grid_color,
        tickfont=dict(color=font_color, size=tick_size),
        title_font=dict(color=font_color, size=13),
    )
    fig.update_yaxes(
        gridcolor=grid_color,
        zerolinecolor=grid_color,
        tickfont=dict(color=font_color, size=tick_size),
        title_font=dict(color=font_color, size=13),
    )
    if pie:
        fig.update_traces(textinfo="percent+label", textposition="inside")
    return fig
