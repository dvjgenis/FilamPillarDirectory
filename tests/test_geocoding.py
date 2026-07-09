"""Tests for directory address collection and geocoding helpers."""

import pandas as pd

from helpers import CHURCH_LOCATIONS, collect_directory_addresses


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
