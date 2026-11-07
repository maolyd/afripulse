"""Exploration: inspect the World Bank API before building ingestion.

This is NOT production code. It answers discovery questions:
  1. How are countries and regions structured?
  2. Does the World Bank's "Africa" match the African Union's Africa?
  3. How complete is each indicator for African countries?
  4. What quirks must the ingestion pipeline handle?

Findings are recorded in docs/discovery/worldbank_findings.md.

Run:  python scripts/explore/explore_worldbank.py
"""

import json
from collections import Counter

import requests

BASE_URL = "https://api.worldbank.org/v2"
TIMEOUT_SECONDS = 30

# The 54 UN-recognised sovereign African states (ISO 3166-1 alpha-3).
# The African Union has 55 members: the 55th, the Sahrawi Arab Democratic
# Republic (Western Sahara), is not listed separately by the World Bank.
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

INDICATORS = {
    "SP.POP.TOTL": "Population, total",
    "NY.GDP.PCAP.CD": "GDP per capita (current US$)",
    "IT.NET.USER.ZS": "Individuals using the Internet (% of population)",
    "FX.OWN.TOTL.ZS": "Account ownership (% of population ages 15+)",
}


def fetch_page(path: str, page: int, **params) -> tuple[dict, list]:
    """Fetch one page from the API and return (metadata, records)."""
    query = {"format": "json", "per_page": 1000, "page": page, **params}
    response = requests.get(f"{BASE_URL}/{path}", params=query, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()  # raise an error on HTTP 4xx / 5xx
    payload = response.json()

    # QUIRK: the World Bank reports some errors with HTTP 200 (success!)
    # and a body like [{"message": [...]}]. raise_for_status() won't catch it.
    if isinstance(payload, list) and len(payload) == 1 and "message" in payload[0]:
        raise RuntimeError(f"World Bank API error: {payload[0]['message']}")

    metadata, records = payload[0], payload[1] or []
    return metadata, records


def fetch_all(path: str, **params) -> tuple[dict, list]:
    """Follow pagination until every page has been collected."""
    metadata, records = fetch_page(path, page=1, **params)
    for page in range(2, int(metadata["pages"]) + 1):
        _, more = fetch_page(path, page=page, **params)
        records.extend(more)
    return metadata, records


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def explore_countries() -> None:
    section("1. COUNTRIES AND REGIONS")
    _, countries = fetch_all("country")

    aggregates = [c for c in countries if c["region"]["value"] == "Aggregates"]
    economies = [c for c in countries if c["region"]["value"] != "Aggregates"]

    print(f"Total records returned:      {len(countries)}")
    print(f"  Aggregates (regions/groups): {len(aggregates)}")
    print(f"  Individual economies:        {len(economies)}")
    print("\nExample aggregates:", [a["name"] for a in aggregates[:6]])

    print("\nOne full country record:")
    kenya = next(c for c in economies if c["id"] == "KEN")
    print(json.dumps(kenya, indent=2))

    section("2. DOES THE WORLD BANK'S AFRICA MATCH OURS?")
    wb_by_iso3 = {c["id"]: c for c in economies}
    ssa = {c["id"] for c in economies if c["region"]["id"] == "SSF"}

    missing_from_wb = sorted(AFRICAN_ISO3 - wb_by_iso3.keys())
    african_outside_ssa = sorted(AFRICAN_ISO3 & wb_by_iso3.keys() - ssa)
    ssa_not_in_our_list = sorted(ssa - AFRICAN_ISO3)

    print(f"Our African list:                   {len(AFRICAN_ISO3)} countries")
    print(f"World Bank 'Sub-Saharan Africa':    {len(ssa)} economies")
    print(f"Missing from World Bank entirely:   {missing_from_wb or 'none'}")
    print("\nAfrican countries NOT in Sub-Saharan Africa region:")
    for iso3 in african_outside_ssa:
        c = wb_by_iso3[iso3]
        print(f"  {iso3}  {c['name']:<25} -> region: {c['region']['value']}")
    print(f"\nIn SSA but not in our list:         {ssa_not_in_our_list or 'none'}")

    income = Counter(
        wb_by_iso3[i]["incomeLevel"]["value"] for i in AFRICAN_ISO3 & wb_by_iso3.keys()
    )
    print("\nAfrican countries by income level:")
    for level, count in income.most_common():
        print(f"  {level:<25} {count}")


def explore_indicator(code: str, label: str) -> None:
    section(f"INDICATOR {code}: {label}")
    countries_param = ";".join(sorted(AFRICAN_ISO3))
    metadata, rows = fetch_all(f"country/{countries_param}/indicator/{code}", date="2000:2025")

    non_null = [r for r in rows if r["value"] is not None]
    null_pct = 100 * (len(rows) - len(non_null)) / len(rows) if rows else 0

    print(f"Source last updated:  {metadata.get('lastupdated')}")
    print(f"Rows returned:        {len(rows)}  (countries x years)")
    print(f"Rows with a value:    {len(non_null)}")
    print(f"Null values:          {null_pct:.1f}%")

    latest_year = {}
    for r in non_null:
        iso3 = r["countryiso3code"]
        latest_year[iso3] = max(latest_year.get(iso3, 0), int(r["date"]))

    no_data = sorted(AFRICAN_ISO3 - latest_year.keys())
    newest = max(latest_year.values(), default=0)
    lagging = {iso3: year for iso3, year in sorted(latest_year.items()) if year < newest}
    print(f"Countries lagging behind {newest}: {lagging or 'none'}")
    years = Counter(latest_year.values())
    print(f"Countries with NO data at all: {no_data or 'none'}")
    print("Most recent year available (year: number of countries):")
    for year, count in sorted(years.items(), reverse=True):
        print(f"  {year}: {count}")

    years_with_data = sorted({int(r["date"]) for r in non_null})
    print(f"Years that have any data: {years_with_data}")

    if non_null:
        print("\nSample record:")
        print(json.dumps(non_null[0], indent=2))


def main() -> None:
    explore_countries()
    for code, label in INDICATORS.items():
        explore_indicator(code, label)
    section("DONE")


if __name__ == "__main__":
    main()
