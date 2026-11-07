"""Profile a downloaded CSV or Excel file: structure, types and completeness.

A reusable discovery tool: one script for every file source, instead of one
script per file. Prints facts only and never modifies the file.

Usage:
    python scripts/explore/profile_file.py PATH [options]

Options:
    --sheet NAME        Excel sheet to read (default: first sheet)
    --header-row N      Row number holding the column names (default: 0)
    --iso3-col COLUMN   Column with ISO3 country codes, to check African coverage
    --year-col COLUMN   Column with years, to show the time range
    --max-columns N     Maximum number of columns to list (default: 80)

Example:
    python scripts/explore/profile_file.py \\
        data/landing/manual/un_wpp/WPP2024_Demographic_Indicators_Medium.csv \\
        --iso3-col ISO3_code --year-col Time
"""

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

AFRICAN_ISO3 = {
    "DZA",
    "AGO",
    "BEN",
    "BWA",
    "BFA",
    "BDI",
    "CPV",
    "CMR",
    "CAF",
    "TCD",
    "COM",
    "COD",
    "COG",
    "CIV",
    "DJI",
    "EGY",
    "GNQ",
    "ERI",
    "SWZ",
    "ETH",
    "GAB",
    "GMB",
    "GHA",
    "GIN",
    "GNB",
    "KEN",
    "LSO",
    "LBR",
    "LBY",
    "MDG",
    "MWI",
    "MLI",
    "MRT",
    "MUS",
    "MAR",
    "MOZ",
    "NAM",
    "NER",
    "NGA",
    "RWA",
    "STP",
    "SEN",
    "SYC",
    "SLE",
    "SOM",
    "ZAF",
    "SSD",
    "SDN",
    "TZA",
    "TGO",
    "TUN",
    "UGA",
    "ZMB",
    "ZWE",
}

EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def is_excel(path: Path) -> bool:
    return path.suffix.lower() in EXCEL_SUFFIXES


def sha256_of(path: Path) -> str:
    """Fingerprint the file in 1 MB chunks, so large files don't fill memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_table(path: Path, sheet: str | None, header_row: int | None, **kwargs) -> pd.DataFrame:
    """Read CSV or Excel. For CSV, fall back to Latin-1 if UTF-8 fails."""
    if is_excel(path):
        return pd.read_excel(path, sheet_name=sheet or 0, header=header_row, **kwargs)
    try:
        return pd.read_csv(path, header=header_row, low_memory=False, **kwargs)
    except UnicodeDecodeError:
        print("NOTE: file is not valid UTF-8; retrying with Latin-1 encoding")
        return pd.read_csv(path, header=header_row, low_memory=False, encoding="latin-1", **kwargs)


def show_file_facts(path: Path) -> None:
    section("1. FILE (for lineage)")
    print(f"Path:     {path}")
    print(f"Size:     {path.stat().st_size / 1_000_000:.2f} MB")
    print(f"SHA-256:  {sha256_of(path)}")


def show_raw_top(path: Path, sheet: str | None) -> None:
    """Show the first rows exactly as stored, to spot titles or notes above the header."""
    section("2. RAW TOP OF FILE (before any header interpretation)")
    if is_excel(path):
        with pd.ExcelFile(path) as book:
            print(f"Sheets: {book.sheet_names}")
    raw = read_table(path, sheet, header_row=None, nrows=8, dtype=str)
    with pd.option_context("display.max_columns", 10, "display.width", 200):
        print(raw)


def show_columns(df: pd.DataFrame, max_columns: int) -> None:
    section("3. SHAPE AND COLUMNS")
    memory_mb = df.memory_usage(deep=True).sum() / 1_000_000
    print(f"Rows: {len(df):,}   Columns: {df.shape[1]}   Memory: {memory_mb:.1f} MB")
    print(f"Fully duplicated rows: {df.duplicated().sum():,}\n")

    print(f"{'#':>3}  {'column':<30}{'dtype':<9}{'null %':>8}{'unique':>9}  example")
    for i, column in enumerate(df.columns[:max_columns]):
        series = df[column]
        non_null = series.dropna()
        example = str(non_null.iloc[0])[:28] if not non_null.empty else ""
        print(
            f"{i:>3}  {str(column)[:29]:<30}{str(series.dtype):<9}"
            f"{100 * series.isna().mean():>7.1f}%{series.nunique():>9}  {example}"
        )

    hidden = df.shape[1] - max_columns
    if hidden > 0:
        print(f"\n... {hidden} more columns not shown (use --max-columns to see more)")
        null_pct = 100 * df.isna().mean()
        print(
            f"Across ALL columns: null % ranges from {null_pct.min():.1f}% to {null_pct.max():.1f}%"
        )
        print(f"Columns that are 100% empty: {(null_pct == 100).sum()}")


def show_country_coverage(df: pd.DataFrame, column: str) -> None:
    section(f"4. COUNTRY COVERAGE (column '{column}')")
    if column not in df.columns:
        print(f"Column not found. Available columns: {list(df.columns)[:15]} ...")
        return

    blank = df[column].isna().sum()
    codes = df[column].dropna().astype(str).str.strip().str.upper()
    present = set(codes)
    african = present & AFRICAN_ISO3

    print(f"Rows with NO code (often regions/aggregates): {blank:,}")
    print(f"Distinct codes in file:                       {len(present)}")
    print(f"African countries present:                    {len(african)} of 54")
    print(
        f"African countries missing:                    {sorted(AFRICAN_ISO3 - present) or 'none'}"
    )
    print(f"African rows:                                 {codes.isin(AFRICAN_ISO3).sum():,}")


def show_year_range(df: pd.DataFrame, column: str) -> None:
    section(f"5. TIME RANGE (column '{column}')")
    if column not in df.columns:
        print("Column not found.")
        return
    years = pd.to_numeric(df[column], errors="coerce")
    print(f"From {int(years.min())} to {int(years.max())}  ({years.nunique()} distinct years)")
    print(f"Non-numeric values: {years.isna().sum() - df[column].isna().sum():,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile a CSV or Excel file.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--sheet")
    parser.add_argument("--header-row", type=int, default=0)
    parser.add_argument("--iso3-col")
    parser.add_argument("--year-col")
    parser.add_argument("--max-columns", type=int, default=80)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.path.is_file():
        sys.exit(f"File not found: {args.path}")

    show_file_facts(args.path)
    show_raw_top(args.path, args.sheet)
    df = read_table(args.path, args.sheet, header_row=args.header_row)
    show_columns(df, args.max_columns)
    if args.iso3_col:
        show_country_coverage(df, args.iso3_col)
    if args.year_col:
        show_year_range(df, args.year_col)
    section("DONE")


if __name__ == "__main__":
    main()
