"""Ingestion jobs: extract -> load -> audit, one function per source.

Each job runs inside track_ingestion_run, so every attempt (successful or not)
is recorded in audit.ingestion_runs. The run_id doubles as the _batch_id on
every raw row written, linking each row to the run that loaded it.

Every job accepts `force`: re-load even if the source looks unchanged.
World Bank jobs always compare row by row (the loader skips unchanged rows),
so `force` only changes behaviour for release-based sources such as the IMF.
"""

import logging
from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import Engine

from afripulse.db.audit import release_already_loaded, track_ingestion_run
from afripulse.db.loader import upsert_records
from afripulse.ingestion.base import ExtractResult
from afripulse.ingestion.extractors.imf import IMFExtractor
from afripulse.ingestion.extractors.worldbank import WorldBankExtractor
from afripulse.ingestion.http_client import HttpClient
from afripulse.sources_config import get_source, load_country_codes

logger = logging.getLogger(__name__)


def _load(engine: Engine, source: dict[str, Any], result: ExtractResult, run) -> None:
    """Shared final step: record counts, load the records, record what was written."""
    run.rows_extracted = len(result.records) + result.rows_rejected
    run.rows_rejected = result.rows_rejected
    run.source_release = result.source_release
    load = upsert_records(
        engine,
        table=source["raw_table"],
        key_columns=source["natural_key"],
        records=result.records,
        batch_id=run.run_id,
        source_release=result.source_release,
    )
    run.rows_loaded = load.loaded


def run_worldbank_countries(
    engine: Engine,
    client: HttpClient,
    source_id: str = "worldbank_countries",
    source: dict[str, Any] | None = None,
    force: bool = False,
) -> None:
    source = source or get_source(source_id)
    with track_ingestion_run(engine, source_id) as run:
        extractor = WorldBankExtractor(client, source["base_url"], source["page_size"])
        _load(engine, source, extractor.extract_countries(), run)


def run_worldbank_wdi(
    engine: Engine,
    client: HttpClient,
    source_id: str = "worldbank_wdi",
    source: dict[str, Any] | None = None,
    country_codes: Sequence[str] | None = None,
    force: bool = False,
) -> None:
    source = source or get_source(source_id)
    country_codes = country_codes or load_country_codes()
    with track_ingestion_run(engine, source_id) as run:
        extractor = WorldBankExtractor(client, source["base_url"], source["page_size"])
        result = extractor.extract_indicators(
            indicator_codes=[indicator["code"] for indicator in source["indicators"]],
            country_codes=country_codes,
            start_year=int(source["start_year"]),
        )
        _load(engine, source, result, run)


def run_imf_weo(
    engine: Engine,
    client: HttpClient,
    source_id: str = "imf_weo",
    source: dict[str, Any] | None = None,
    country_codes: Sequence[str] | None = None,
    force: bool = False,
) -> None:
    """Load the current WEO release, unless it was already loaded (skipped)."""
    source = source or get_source(source_id)
    country_codes = country_codes or load_country_codes()
    indicator_codes = [indicator["code"] for indicator in source["indicators"]]

    with track_ingestion_run(engine, source_id) as run:
        extractor = IMFExtractor(client, source["base_url"])
        release = extractor.detect_release(indicator_codes)
        run.source_release = release

        if not force and release_already_loaded(engine, source_id, release):
            logger.info("IMF release %s already loaded: skipping (use --force to reload)", release)
            run.status = "skipped"
            return

        result = extractor.extract(indicator_codes, country_codes, release)
        _load(engine, source, result, run)


# Source id -> job. New sources are added here as their extractors are built.
JOBS: dict[str, Callable[..., None]] = {
    "worldbank_countries": run_worldbank_countries,
    "worldbank_wdi": run_worldbank_wdi,
    "imf_weo": run_imf_weo,
}
