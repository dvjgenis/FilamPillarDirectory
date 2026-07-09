"""Tests for directory address collection and geocoding helpers."""

import pandas as pd

from helpers import (
    CHURCH_LOCATIONS,
    collect_directory_addresses,
    is_map_display_coordinate,
    out_of_region_geocoded_addresses,
)


def test_collect_directory_addresses_includes_churches():
    addresses = collect_directory_addresses()
    assert set(CHURCH_LOCATIONS.values()).issubset(set(addresses))


def test_collect_directory_addresses_includes_households():
    df = pd.DataFrame(
        {
            "Home_Address": [
                "123 Main St, Chicago, IL",
                None,
                "",
                "Not available",
            ]
        }
    )
    addresses = collect_directory_addresses(df)
    assert "123 Main St, Chicago, IL" in addresses
    assert "Not available" not in addresses


def test_is_map_display_coordinate_accepts_chicagoland():
    assert is_map_display_coordinate(41.9, -87.7) is True


def test_is_map_display_coordinate_rejects_international():
    assert is_map_display_coordinate(9.31, 123.31) is False


def test_geocode_missing_count_uses_cache():
    from helpers import geocode_missing_count

    df = pd.DataFrame({"Home_Address": ["123 Main St, Chicago, IL", "456 Oak Ave, Naperville, IL"]})
    mapped, total = geocode_missing_count(df)
    assert total >= 2 + 2  # households + 2 church addresses
    assert 0 <= mapped <= total


def test_ensure_map_geocoded_returns_tuple():
    from helpers import ensure_map_geocoded

    df = pd.DataFrame({"Home_Address": []})
    ok, err = ensure_map_geocoded(df)
    assert ok is True
    assert err is None


def test_out_of_region_geocoded_addresses():
    cache = {
        "Chicago, IL": {"lat": 41.9, "lng": -87.7},
        "Philippines": {"lat": 9.31, "lng": 123.31},
        "Missing": {"lat": None, "lng": None},
    }
    excluded = out_of_region_geocoded_addresses(
        ["Chicago, IL", "Philippines", "Missing"],
        cache,
    )
    assert excluded == ["Philippines"]
