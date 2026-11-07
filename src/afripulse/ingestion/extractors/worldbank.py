"""Extract data from the World Bank API v2.

Handles the quirks found in discovery (docs/discovery/worldbank_findings.md):
  F1   /country mixes countries and aggregates: kept in raw, filtered in staging
  F4   ISO3 (countryiso3code) is the key, not the ISO2 country.id
  F11  null values are kept in raw
  F12  'lastupdated' is recorded as the source release
  F13  errors can arrive with HTTP 200 and a 'message' body
"""

import logging
from collections.abc import Iterator, Sequence
from datetime import date
from typing import Any

from afripulse.ingestion.base import ExtractResult, Record
from afripulse.ingestion.http_client import HttpClient

logger = logging.getLogger(__name__)


class WorldBankAPIError(RuntimeError):
    """The API answered, but with an error message instead of data (F13)."""


class WorldBankExtractor:
    def __init__(self, client: HttpClient, base_url: str, page_size: int = 1000) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.page_size = page_size

    def _pages(self, path: str, **params: Any) -> Iterator[tuple[dict, list[dict], str]]:
        """Yield (metadata, records, url) for every page of a World Bank endpoint."""
        url = f"{self.base_url}/{path}"
        page, pages = 1, 1
        while page <= pages:
            query = {"format": "json", "per_page": self.page_size, "page": page, **params}
            payload = self.client.get_json(url, query)
            if isinstance(payload, list) and len(payload) == 1 and "message" in payload[0]:
                raise WorldBankAPIError(f"{url}: {payload[0]['message']}")
            metadata, records = payload[0], payload[1] or []
            pages = int(metadata["pages"])
            logger.debug("%s page %d/%d: %d records", path, page, pages, len(records))
            yield metadata, records, url
            page += 1

    def extract_countries(self) -> ExtractResult:
        result = ExtractResult()
        for _, records, url in self._pages("country"):
            for record in records:
                result.records.append(
                    {"country_code": record["id"], "payload": record, "_source_url": url}
                )
        logger.info("World Bank countries: %d records", len(result.records))
        return result

    def extract_indicators(
        self,
        indicator_codes: Sequence[str],
        country_codes: Sequence[str],
        start_year: int,
        end_year: int | None = None,
    ) -> ExtractResult:
        end_year = end_year or date.today().year
        countries = ";".join(country_codes)
        result = ExtractResult()
        releases: list[str] = []

        for code in indicator_codes:
            before = len(result.records)
            path = f"country/{countries}/indicator/{code}"
            for metadata, rows, url in self._pages(path, date=f"{start_year}:{end_year}"):
                release = metadata.get("lastupdated")
                if release:
                    releases.append(release)
                for row in rows:
                    record = self._indicator_record(code, row, url, release)
                    if record is None:
                        result.rows_rejected += 1
                    else:
                        result.records.append(record)
            logger.info("Indicator %s: %d records", code, len(result.records) - before)

        result.source_release = max(releases) if releases else None
        return result

    @staticmethod
    def _indicator_record(code: str, row: dict, url: str, release: str | None) -> Record | None:
        iso3 = (row.get("countryiso3code") or "").strip()
        year = str(row.get("date") or "")
        if len(iso3) != 3 or not year.isdigit():
            logger.warning("Rejected %s row with iso3=%r date=%r", code, iso3, year)
            return None
        return {
            "indicator_code": code,
            "country_iso3": iso3,
            "year": int(year),
            "payload": row,
            "_source_url": url,
            "_source_release": release,
        }
