#!/usr/bin/env python3
"""Pre-geocode directory addresses for local cache or Streamlit Cloud secrets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from helpers import (  # noqa: E402
    GEOCODE_CACHE_PATH,
    collect_directory_addresses,
    ensure_directory_geocoded,
    load_and_clean,
    load_geocode_cache,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-geocode all directory addresses.")
    parser.add_argument(
        "--print-secrets",
        action="store_true",
        help="Print TOML-ready geocode_cache JSON for Streamlit secrets instead of only writing the file.",
    )
    args = parser.parse_args()

    df = load_and_clean()
    addresses = collect_directory_addresses(df)
    before = load_geocode_cache()
    mapped_before = sum(1 for a in addresses if before.get(a, {}).get("lat") is not None)

    print(f"Directory addresses: {len(addresses)} ({mapped_before} already mapped)")
    ensure_directory_geocoded(df)

    cache = load_geocode_cache()
    mapped_after = sum(1 for a in addresses if cache.get(a, {}).get("lat") is not None)
    failed = [a for a in addresses if cache.get(a, {}).get("error")]

    print(f"Mapped: {mapped_after}/{len(addresses)}")
    print(f"Cache file: {GEOCODE_CACHE_PATH} ({GEOCODE_CACHE_PATH.stat().st_size if GEOCODE_CACHE_PATH.exists() else 0} bytes)")
    if failed:
        print(f"Failed ({len(failed)}):")
        for address in failed[:10]:
            print(f"  - {address}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")

    if args.print_secrets:
        print("\n# Paste into Streamlit secrets as [geocode_cache] (JSON object):")
        print("[geocode_cache]")
        print(json.dumps(cache, indent=2))

    return 0 if mapped_after > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
