"""Ingestion jobs: extract -> load -> audit, one function per source.

Each job runs inside track_ingestion_run, so every attempt (successful or not)
is recorded in audit.ingestion_runs. Before anything is loaded, the records are
validated (afripulse.validation): error-level failures block the load.
The run_id doubles as the _batch_id on every raw row written, linking each
row to the run that loaded it.

Every job accepts `force`: re-load even if the source looks unchanged.
World Bank jobs always compare row by row (the loader skips unchanged rows),
so `force` only changes behaviour for release-based sources such as the IMF.
"""

import logging
from collections.abc import Callable, Sequence
from functools import partial
from typing import Any

from sqlalchemy import Engine

from afripulse.config import PROJECT_ROOT
from afripulse.db.audit import (
    checksum_already_loaded,
    release_already_loaded,
    track_ingestion_run,
)
from afripulse.db.loader import upsert_records
from afripulse.ingestion.base import ExtractResult
from afripulse.ingestion.extractors.files import FileExtractor
from afripulse.ingestion.extractors.imf import IMFExtractor
from afripulse.ingestion.extractors.worldbank import WorldBankExtractor
from afripulse.ingestion.http_client import HttpClient
from afripulse.sources_config import get_source, load_country_codes
from afripulse.validation.checks import DataValidationError, validate_records
from afripulse.validation.store import previous_row_count, save_validation_report

logger = logging.getLogger(__name__)


def _load(
    engine: Engine,
    source: dict[str, Any],
    result: ExtractResult,
    run,
    country_codes: Sequence[str] | None = None,
) -> None:
    """Shared final steps: record counts, validate, then load."""
    run.rows_extracted = len(result.records) + result.rows_rejected
    run.rows_rejected = result.rows_rejected
    run.source_release = result.source_release

    report = validate_records(
        result.records,
        rules=source.get("validation", {}),
        key_columns=source["natural_key"],
        reference_countries=set(country_codes or []),
        previous_count=previous_row_count(engine, run.source_id, run.run_id),
    )
    save_validation_report(engine, run.run_id, report)
    if report.failed_errors:
        raise DataValidationError(f"Validation failed, nothing loaded: {report.summary()}")

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
        _load(engine, source, result, run, country_codes)


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
        _load(engine, source, result, run, country_codes)


def run_file_source(
    engine: Engine,
    client: HttpClient | None = None,
    source_id: str = "",
    source: dict[str, Any] | None = None,
    country_codes: Sequence[str] | None = None,
    force: bool = False,
) -> None:
    """Load a downloaded CSV/Excel file, unless this exact file was already loaded.

    `client` is unused (files need no HTTP) but accepted so every job has the
    same call signature.
    """
    source = source or get_source(source_id)
    country_codes = country_codes or load_country_codes()
    hint = f" from {source['download_page']}" if source.get("download_page") else ""

    with track_ingestion_run(engine, source_id) as run:
        extractor = FileExtractor(PROJECT_ROOT / source["landing_path"], source, hint)
        run.source_checksum = extractor.checksum()
        run.source_release = source["release"]

        if not force and checksum_already_loaded(engine, source_id, run.source_checksum):
            logger.info("%s: file unchanged since last load, skipping", source_id)
            run.status = "skipped"
            return

        result = extractor.extract(country_codes, source["release"])
        _load(engine, source, result, run, country_codes)


# Source id -> job. New sources are added here as their extractors are built.
JOBS: dict[str, Callable[..., None]] = {
    "worldbank_countries": run_worldbank_countries,
    "worldbank_wdi": run_worldbank_wdi,
    "imf_weo": run_imf_weo,
    "un_wpp": partial(run_file_source, source_id="un_wpp"),
    "findex": partial(run_file_source, source_id="findex"),
}
