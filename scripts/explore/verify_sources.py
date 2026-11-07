"""Verify every enabled source in config/sources.yml.

  - API sources: the endpoint responds and every configured indicator exists.
  - File sources: the landing file is present.

Exits with status 1 if anything fails, so it can be used in automation.

Run:  python scripts/explore/verify_sources.py
"""

import sys
from pathlib import Path

import requests
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.yml"
TIMEOUT_SECONDS = 30


def check_worldbank_indicator(base_url: str, code: str) -> tuple[bool, str]:
    response = requests.get(
        f"{base_url}/indicator/{code}", params={"format": "json"}, timeout=TIMEOUT_SECONDS
    )
    response.raise_for_status()
    payload = response.json()
    if len(payload) == 1 and "message" in payload[0]:  # HTTP 200 error (F13)
        return False, f"invalid code: {payload[0]['message'][0].get('value')}"
    record = payload[1][0]
    upstream = " ".join(record.get("sourceOrganization", "?").split())[:55]
    return True, f"{record['name'][:45]}  | upstream: {upstream}"


def check_worldbank_endpoint(base_url: str, endpoint: str) -> tuple[bool, str]:
    response = requests.get(
        f"{base_url}/{endpoint}", params={"format": "json", "per_page": 1}, timeout=TIMEOUT_SECONDS
    )
    response.raise_for_status()
    metadata = response.json()[0]
    return True, f"{metadata['total']} records available"


def verify_source(name: str, source: dict) -> int:
    """Print results for one source and return the number of failures."""
    print(f"\n[{name}]  connector={source['connector']}")
    failures = 0
    connector = source["connector"]

    try:
        if connector == "worldbank_api" and "endpoint" in source:
            ok, detail = check_worldbank_endpoint(source["base_url"], source["endpoint"])
            print(f"  {'OK ' if ok else 'FAIL'}  {source['endpoint']}: {detail}")
            failures += not ok

        elif connector == "worldbank_api":
            for indicator in source["indicators"]:
                ok, detail = check_worldbank_indicator(source["base_url"], indicator["code"])
                print(f"  {'OK ' if ok else 'FAIL'}  {indicator['code']:<20} {detail}")
                failures += not ok

        elif connector == "imf_datamapper_api":
            response = requests.get(f"{source['base_url']}/indicators", timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            available = response.json()["indicators"]
            for indicator in source["indicators"]:
                meta = available.get(indicator["code"])
                ok = meta is not None
                detail = f"{meta['label']} | {meta.get('source')}" if ok else "not found"
                print(f"  {'OK ' if ok else 'FAIL'}  {indicator['code']:<20} {detail}")
                failures += not ok

        elif connector in {"csv_file", "excel_file"}:
            path = PROJECT_ROOT / source["landing_path"]
            ok = path.is_file()
            detail = f"{path.stat().st_size / 1_000_000:.1f} MB" if ok else "MISSING"
            print(f"  {'OK ' if ok else 'FAIL'}  {source['landing_path']} ({detail})")
            failures += not ok

        else:
            print(f"  FAIL  unknown connector '{connector}'")
            failures += 1

    except requests.RequestException as error:
        print(f"  FAIL  request error: {error}")
        failures += 1

    return failures


def main() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    total_failures = 0
    for name, source in config["sources"].items():
        if not source.get("enabled", True):
            print(f"\n[{name}]  skipped (disabled)")
            continue
        total_failures += verify_source(name, source)

    print(f"\n{'=' * 70}")
    if total_failures:
        print(f"FAILED: {total_failures} check(s) failed")
        sys.exit(1)
    print("ALL SOURCES VERIFIED")


if __name__ == "__main__":
    main()
