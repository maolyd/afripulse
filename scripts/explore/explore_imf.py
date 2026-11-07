"""Exploration: inspect the IMF DataMapper API and compare it with the World Bank.

This is NOT production code. It answers discovery questions:
  1. What does the IMF API offer, and how is it structured?
  2. Does it cover all 54 African countries?
  3. Which years are actual data and which are projections?
  4. Do the IMF and World Bank agree on GDP growth?

Run:  python scripts/explore/explore_imf.py
"""

import json
from statistics import mean

import requests

IMF_BASE = "https://www.imf.org/external/datamapper/api/v1"
WB_BASE = "https://api.worldbank.org/v2"
TIMEOUT_SECONDS = 30


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

IMF_INDICATORS = ["NGDP_RPCH", "PCPIPCH"]  # real GDP growth, inflation
COMPARE_YEARS = range(2015, 2025)  # years where both sources hold actual data


def get_json(url: str, **params) -> dict | list:
    response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def explore_catalogue() -> set[str]:
    """Show what the API offers. Returns the set of IMF country codes."""
    section("1. WHAT DOES THE IMF API OFFER?")
    indicators = get_json(f"{IMF_BASE}/indicators")["indicators"]
    print(f"Indicators available: {len(indicators)}")

    for code in IMF_INDICATORS:
        meta = indicators.get(code, {})
        print(f"\n  {code}")
        print(f"    label:  {meta.get('label')}")
        print(f"    unit:   {meta.get('unit')}")
        print(f"    source: {meta.get('source')}")

    countries = get_json(f"{IMF_BASE}/countries")["countries"]
    print(f"\nCountry codes in IMF list: {len(countries)}")
    print("Sample entry:", json.dumps({"KEN": countries.get("KEN")}))

    missing = sorted(AFRICAN_ISO3 - countries.keys())
    print(f"Our African countries missing from IMF list: {missing or 'none'}")
    return set(countries.keys())


def fetch_imf_series(code: str) -> dict[str, dict[int, float]]:
    """Return {area_code: {year: value}} for one indicator, nulls removed."""
    payload = get_json(f"{IMF_BASE}/{code}")
    series = payload.get("values", {}).get(code, {})
    return {
        area: {int(year): value for year, value in years.items() if value is not None}
        for area, years in series.items()
    }


def explore_indicator(code: str, imf_countries: set[str]) -> dict[str, dict[int, float]]:
    section(f"INDICATOR {code}")
    data = fetch_imf_series(code)

    not_countries = sorted(set(data) - imf_countries)
    african = {area: years for area, years in data.items() if area in AFRICAN_ISO3}
    missing = sorted(AFRICAN_ISO3 - african.keys())

    print(f"Areas returned:                {len(data)}")
    print(f"  of which are NOT countries:  {len(not_countries)}  e.g. {not_countries[:8]}")
    print(f"African countries with data:   {len(african)}")
    print(f"African countries missing:     {missing or 'none'}")

    all_years = sorted({year for years in african.values() for year in years})
    if all_years:
        print(f"Year range:                    {all_years[0]} - {all_years[-1]}")
        future = [year for year in all_years if year >= 2026]
        print(f"Years from 2026 onwards:       {future}")

    kenya = sorted(african.get("KEN", {}).items())
    print(f"\nKenya, last 10 years returned: {dict(kenya[-10:])}")
    return african


def fetch_world_bank_growth() -> dict[tuple[str, int], float]:
    """World Bank GDP growth (annual %) for African countries, as {(iso3, year): value}."""
    countries = ";".join(sorted(AFRICAN_ISO3))
    payload = get_json(
        f"{WB_BASE}/country/{countries}/indicator/NY.GDP.MKTP.KD.ZG",
        format="json",
        per_page=2000,
        date=f"{COMPARE_YEARS.start}:{COMPARE_YEARS.stop - 1}",
    )
    metadata, rows = payload[0], payload[1] or []
    if int(metadata["pages"]) > 1:
        raise RuntimeError("Unexpected pagination: increase per_page")
    return {
        (row["countryiso3code"], int(row["date"])): row["value"]
        for row in rows
        if row["value"] is not None
    }


def compare_sources(imf_growth: dict[str, dict[int, float]]) -> None:
    section("COMPARISON: IMF NGDP_RPCH vs WORLD BANK NY.GDP.MKTP.KD.ZG")
    wb_growth = fetch_world_bank_growth()

    pairs = []
    for (iso3, year), wb_value in wb_growth.items():
        imf_value = imf_growth.get(iso3, {}).get(year)
        if imf_value is not None:
            pairs.append((abs(imf_value - wb_value), iso3, year, imf_value, wb_value))

    if not pairs:
        print("No overlapping values found.")
        return

    gaps = [pair[0] for pair in pairs]
    within_half_pp = sum(gap <= 0.5 for gap in gaps)
    print(f"Country-years compared:         {len(pairs)}")
    print(f"Mean absolute difference:       {mean(gaps):.2f} percentage points")
    print(f"Within 0.5 pp of each other:    {100 * within_half_pp / len(pairs):.1f}%")
    print(f"Differ by more than 2 pp:       {sum(gap > 2 for gap in gaps)}")

    print("\nTop 10 disagreements:")
    print(f"  {'Country':<8}{'Year':<6}{'IMF':>8}{'WB':>8}{'Gap':>8}")
    for gap, iso3, year, imf_value, wb_value in sorted(pairs, reverse=True)[:10]:
        print(f"  {iso3:<8}{year:<6}{imf_value:>8.2f}{wb_value:>8.2f}{gap:>8.2f}")


def main() -> None:
    imf_countries = explore_catalogue()
    results = {code: explore_indicator(code, imf_countries) for code in IMF_INDICATORS}
    compare_sources(results["NGDP_RPCH"])
    section("DONE")


if __name__ == "__main__":
    main()
