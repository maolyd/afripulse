"""Extract World Economic Outlook data from the IMF DataMapper API.

Handles the quirks found in discovery (docs/discovery/imf_findings.md):
  F-IMF-1  custom User-Agents are blocked: HttpClient sends the standard one
  F-IMF-3  values belong to a WEO release, detected from the API itself
  F-IMF-4  aggregates (AFQ, ADVEC...) are dropped: only reference countries kept
  F-IMF-5  projections are loaded as received; flagged later in staging
"""

import logging
import re
from collections.abc import Sequence

from afripulse.ingestion.base import ExtractResult
from afripulse.ingestion.http_client import HttpClient

logger = logging.getLogger(__name__)

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
# e.g. "World Economic Outlook (October 2026)"
_RELEASE_PATTERN = re.compile(r"World Economic Outlook \((\w+) (\d{4})\)", re.IGNORECASE)


class IMFAPIError(RuntimeError):
    """The IMF API answered, but not with what the pipeline expects."""


def parse_release(source_label: str) -> str:
    """'World Economic Outlook (October 2026)' -> 'WEO-2026-10'."""
    match = _RELEASE_PATTERN.search(source_label or "")
    if not match or match.group(1).lower() not in MONTHS:
        raise IMFAPIError(f"Cannot read a WEO release from source label {source_label!r}")
    month = MONTHS[match.group(1).lower()]
    return f"WEO-{match.group(2)}-{month:02d}"


class IMFExtractor:
    def __init__(self, client: HttpClient, base_url: str) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")

    def detect_release(self, indicator_codes: Sequence[str]) -> str:
        """Ask the API which WEO release the indicators currently come from."""
        catalogue = self.client.get_json(f"{self.base_url}/indicators")["indicators"]
        missing = [code for code in indicator_codes if code not in catalogue]
        if missing:
            raise IMFAPIError(f"Indicators not offered by the IMF API: {missing}")
        labels = {catalogue[code].get("source", "") for code in indicator_codes}
        if len(labels) != 1:
            raise IMFAPIError(f"Indicators come from different releases: {sorted(labels)}")
        release = parse_release(labels.pop())
        logger.info("IMF current release: %s", release)
        return release

    def extract(
        self, indicator_codes: Sequence[str], country_codes: Sequence[str], release: str
    ) -> ExtractResult:
        in_scope = set(country_codes)
        result = ExtractResult(source_release=release)

        for code in indicator_codes:
            url = f"{self.base_url}/{code}"
            series = self.client.get_json(url).get("values", {}).get(code)
            if series is None:
                raise IMFAPIError(f"No values returned for indicator {code}")

            before = len(result.records)
            for area, years in series.items():
                if area not in in_scope:  # aggregates and non-African countries
                    continue
                for year, value in years.items():
                    if not str(year).isdigit():
                        logger.warning("Rejected %s/%s value with year %r", code, area, year)
                        result.rows_rejected += 1
                        continue
                    if value is None:
                        continue
                    result.records.append(
                        {
                            "release": release,
                            "indicator_code": code,
                            "area_code": area,
                            "year": int(year),
                            "payload": {
                                "indicator": code,
                                "area": area,
                                "year": str(year),
                                "value": value,
                            },
                            "_source_url": url,
                        }
                    )
            logger.info("Indicator %s: %d records", code, len(result.records) - before)
        return result
