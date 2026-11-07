"""Data contract tests for the African countries reference file.

The file is the single source of truth for which countries AfriPulse covers,
so its shape and rules are protected by tests. See ADR 0001.
"""

import csv
import re
from collections import Counter
from pathlib import Path

import pytest

REFERENCE_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "reference" / "african_countries.csv"
)
EXCLUDED_TERRITORIES = {"ESH", "MYT", "REU", "SHN"}


@pytest.fixture(scope="module")
def rows() -> list[dict[str, str]]:
    # The csv module reads every value as text: "NA" (Namibia) stays "NA".
    with REFERENCE_FILE.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_has_exactly_54_countries(rows):
    assert len(rows) == 54


def test_iso3_codes_are_unique_and_well_formed(rows):
    codes = [row["iso3"] for row in rows]
    assert len(set(codes)) == len(codes)
    assert all(re.fullmatch(r"[A-Z]{3}", code) for code in codes)


def test_iso2_codes_are_unique_and_well_formed(rows):
    codes = [row["iso2"] for row in rows]
    assert len(set(codes)) == len(codes)
    assert all(re.fullmatch(r"[A-Z]{2}", code) for code in codes)


def test_namibia_iso2_is_not_lost(rows):
    """Regression test for discovery finding F-UN-3."""
    namibia = next(row for row in rows if row["iso3"] == "NAM")
    assert namibia["iso2"] == "NA"


def test_au_region_counts(rows):
    counts = Counter(row["au_region"] for row in rows)
    assert counts == {"Northern": 6, "Western": 15, "Central": 9, "Eastern": 14, "Southern": 10}


def test_excluded_territories_are_absent(rows):
    codes = {row["iso3"] for row in rows}
    assert codes.isdisjoint(EXCLUDED_TERRITORIES)


def test_every_country_has_a_display_name(rows):
    assert all(row["country_name"].strip() for row in rows)
