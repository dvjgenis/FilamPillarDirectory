"""Tests for directory address collection and geocoding helpers."""

import pandas as pd

from helpers import (
    CHURCH_LOCATIONS,
    collect_directory_addresses,
    compute_regional_view_state,
    is_map_display_coordinate,
    out_of_region_geocoded_addresses,
    prepare_map_frame,
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


def test_prepare_map_frame_drops_out_of_region_rows():
    frame = pd.DataFrame(
        {
            "lat": [41.9, 9.31, "bad"],
            "lng": [-87.7, 123.31, -88.0],
        }
    )
    filtered = prepare_map_frame(frame)
    assert len(filtered) == 1
    assert filtered.iloc[0]["lat"] == 41.9


def test_compute_regional_view_state_ignores_outliers():
    chicagoland = pd.DataFrame({"lat": [41.9, 41.7], "lng": [-87.7, -88.2]})
    outlier = pd.DataFrame({"lat": [9.31], "lng": [123.31]})
    view = compute_regional_view_state(chicagoland, outlier)
    assert 41.0 < view["latitude"] < 42.0
    assert -89.0 < view["longitude"] < -87.0
    assert view["zoom"] >= 6.5


def test_compute_regional_view_state_falls_back_to_chicago():
    view = compute_regional_view_state(pd.DataFrame())
    assert view["latitude"] == 41.8781
    assert view["longitude"] == -87.6298
    assert view["zoom"] == 8.0


def test_build_church_map_data_skips_out_of_region_cache_entries():
    from helpers import build_church_map_data

    cache = {
        list(CHURCH_LOCATIONS.values())[0]: {"lat": 41.9, "lng": -87.7},
        list(CHURCH_LOCATIONS.values())[1]: {"lat": 9.31, "lng": 123.31},
    }
    church_df = build_church_map_data(cache)
    assert len(church_df) == 1
    assert church_df.iloc[0]["lat"] == 41.9
