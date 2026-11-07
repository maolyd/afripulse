"""Build the AfriPulse African countries reference file.

Combines two inputs:
  1. A curated list of the 54 African Union member states recognised as
     sovereign by the UN, with display names and AU regions (maintained here).
  2. Codes and attributes from the World Bank country API (authoritative).

Output: data/reference/african_countries.csv (committed to Git).
Scoping decisions: docs/adr/0001-definition-of-africa.md

Run:  python scripts/reference/build_country_reference.py
"""

import csv
import sys
from collections import Counter
from pathlib import Path

import requests

WB_COUNTRY_URL = "https://api.worldbank.org/v2/country"
TIMEOUT_SECONDS = 30
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "data" / "reference" / "african_countries.csv"

# iso3: (display name, African Union region)
AU_MEMBER_STATES = {
    # Northern
    "DZA": ("Algeria", "Northern"),
    "EGY": ("Egypt", "Northern"),
    "LBY": ("Libya", "Northern"),
    "MRT": ("Mauritania", "Northern"),
    "MAR": ("Morocco", "Northern"),
    "TUN": ("Tunisia", "Northern"),
    # Western
    "BEN": ("Benin", "Western"),
    "BFA": ("Burkina Faso", "Western"),
    "CPV": ("Cabo Verde", "Western"),
    "CIV": ("Côte d'Ivoire", "Western"),
    "GMB": ("The Gambia", "Western"),
    "GHA": ("Ghana", "Western"),
    "GIN": ("Guinea", "Western"),
    "GNB": ("Guinea-Bissau", "Western"),
    "LBR": ("Liberia", "Western"),
    "MLI": ("Mali", "Western"),
    "NER": ("Niger", "Western"),
    "NGA": ("Nigeria", "Western"),
    "SEN": ("Senegal", "Western"),
    "SLE": ("Sierra Leone", "Western"),
    "TGO": ("Togo", "Western"),
    # Central
    "BDI": ("Burundi", "Central"),
    "CMR": ("Cameroon", "Central"),
    "CAF": ("Central African Republic", "Central"),
    "TCD": ("Chad", "Central"),
    "COG": ("Republic of the Congo", "Central"),
    "COD": ("DR Congo", "Central"),
    "GNQ": ("Equatorial Guinea", "Central"),
    "GAB": ("Gabon", "Central"),
    "STP": ("São Tomé and Príncipe", "Central"),
    # Eastern
    "COM": ("Comoros", "Eastern"),
    "DJI": ("Djibouti", "Eastern"),
    "ERI": ("Eritrea", "Eastern"),
    "ETH": ("Ethiopia", "Eastern"),
    "KEN": ("Kenya", "Eastern"),
    "MDG": ("Madagascar", "Eastern"),
    "MUS": ("Mauritius", "Eastern"),
    "RWA": ("Rwanda", "Eastern"),
    "SYC": ("Seychelles", "Eastern"),
    "SOM": ("Somalia", "Eastern"),
    "SSD": ("South Sudan", "Eastern"),
    "SDN": ("Sudan", "Eastern"),
    "TZA": ("Tanzania", "Eastern"),
    "UGA": ("Uganda", "Eastern"),
    # Southern
    "AGO": ("Angola", "Southern"),
    "BWA": ("Botswana", "Southern"),
    "SWZ": ("Eswatini", "Southern"),
    "LSO": ("Lesotho", "Southern"),
    "MWI": ("Malawi", "Southern"),
    "MOZ": ("Mozambique", "Southern"),
    "NAM": ("Namibia", "Southern"),
    "ZAF": ("South Africa", "Southern"),
    "ZMB": ("Zambia", "Southern"),
    "ZWE": ("Zimbabwe", "Southern"),
}

EXPECTED_REGION_COUNTS = {
    "Northern": 6,
    "Western": 15,
    "Central": 9,
    "Eastern": 14,
    "Southern": 10,
}

COLUMNS = [
    "iso3",
    "iso2",
    "country_name",
    "country_name_wb",
    "au_region",
    "capital_city",
    "latitude",
    "longitude",
]


def fetch_world_bank_countries() -> dict[str, dict]:
    """Return World Bank country records keyed by ISO3 code."""
    response = requests.get(
        WB_COUNTRY_URL, params={"format": "json", "per_page": 400}, timeout=TIMEOUT_SECONDS
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or len(payload) != 2:
        raise RuntimeError(f"Unexpected World Bank response: {str(payload)[:200]}")
    metadata, records = payload
    if int(metadata["pages"]) > 1:
        raise RuntimeError("World Bank country list spans several pages: raise per_page")
    return {record["id"]: record for record in records}


def build_rows(wb_countries: dict[str, dict]) -> list[dict[str, str]]:
    rows = []
    for iso3 in sorted(AU_MEMBER_STATES):
        display_name, au_region = AU_MEMBER_STATES[iso3]
        wb = wb_countries[iso3]
        rows.append(
            {
                "iso3": iso3,
                "iso2": wb["iso2Code"],
                "country_name": display_name,
                "country_name_wb": wb["name"].strip(),
                "au_region": au_region,
                "capital_city": wb["capitalCity"].strip(),
                "latitude": wb["latitude"],
                "longitude": wb["longitude"],
            }
        )
    return rows


def validate(wb_countries: dict[str, dict]) -> None:
    """Stop with a clear message if any input is inconsistent."""
    errors = []

    missing = sorted(set(AU_MEMBER_STATES) - wb_countries.keys())
    if missing:
        errors.append(f"Not found in World Bank country list: {missing}")

    region_counts = Counter(region for _, region in AU_MEMBER_STATES.values())
    if dict(region_counts) != EXPECTED_REGION_COUNTS:
        errors.append(f"AU region counts {dict(region_counts)} != {EXPECTED_REGION_COUNTS}")

    if len(AU_MEMBER_STATES) != 54:
        errors.append(f"Expected 54 countries, found {len(AU_MEMBER_STATES)}")

    if errors:
        sys.exit("VALIDATION FAILED:\n  - " + "\n  - ".join(errors))


def write_csv(rows: list[dict[str, str]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    wb_countries = fetch_world_bank_countries()
    validate(wb_countries)
    rows = build_rows(wb_countries)

    duplicate_iso2 = [code for code, n in Counter(r["iso2"] for r in rows).items() if n > 1]
    if duplicate_iso2:
        sys.exit(f"VALIDATION FAILED: duplicate ISO2 codes {duplicate_iso2}")

    write_csv(rows)
    print(f"Wrote {len(rows)} countries to {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    for region, count in sorted(Counter(r["au_region"] for r in rows).items()):
        print(f"  {region:<9} {count}")


if __name__ == "__main__":
    main()
