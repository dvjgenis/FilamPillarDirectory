#!/usr/bin/env python3
"""Clean directory CSV: remove blank rows and report data quality issues."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from helpers import CSV_COLUMNS, CSV_PATH, audit_data_quality

DEFAULT_CSV = ROOT / "Filam_Pillar Church Directory - Main.csv"


def clean_csv(csv_path: Path, *, dry_run: bool = False) -> tuple[int, int]:
    """Remove blank rows; optionally write cleaned file with backup."""
    df = pd.read_csv(csv_path)
    missing_cols = [c for c in CSV_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"CSV missing expected columns: {missing_cols}")

    before = len(df)
    cleaned = df[
        df["First_Name"].notna()
        & (df["First_Name"].astype(str).str.strip() != "")
    ].reset_index(drop=True)
    after = len(cleaned)

    issues = audit_data_quality(cleaned)
    print(f"Rows before: {before}")
    print(f"Rows after:  {after}")
    print(f"Removed:     {before - after} blank rows")
    print()
    print("Data quality summary:")
    print(f"  Missing birthdays: {len(issues['missing_birthdays'])}")
    print(f"  Missing phones:    {len(issues['missing_phones'])}")
    print(f"  Missing emails:    {len(issues['missing_emails'])}")
    print(f"  Children mismatches: {len(issues['children_mismatches'])}")
    print(f"  Invalid birthdays: {len(issues['invalid_birthdays'])}")
    print(f"  Invalid anniversaries: {len(issues['invalid_anniversaries'])}")

    if issues["children_mismatches"]:
        print("\nChildren name/birthday mismatches:")
        for item in issues["children_mismatches"][:20]:
            print(f"  - {item}")

    if not dry_run and after < before:
        backup = csv_path.with_suffix(csv_path.suffix + ".bak")
        shutil.copy2(csv_path, backup)
        cleaned.to_csv(csv_path, index=False)
        print(f"\nWrote cleaned CSV to {csv_path}")
        print(f"Backup saved to {backup}")

    return before, after


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean church directory CSV")
    parser.add_argument(
        "--csv",
        type=Path,
        default=CSV_PATH if CSV_PATH.exists() else DEFAULT_CSV,
        help="Path to directory CSV",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    clean_csv(args.csv, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
