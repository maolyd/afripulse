"""Record every ingestion run in audit.ingestion_runs.

Usage:
    with track_ingestion_run(engine, "worldbank_wdi") as run:
        rows = extract(...)
        run.rows_extracted = len(rows)
        run.rows_loaded = load(rows)

On normal exit the run is marked 'success' (or 'skipped' if the code set it).
If the block raises an exception, the run is marked 'failed' with the error
message, and the exception is re-raised so the caller still sees the failure.
"""

import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)

FINAL_STATUSES = {"success", "skipped"}
MAX_ERROR_LENGTH = 2000


@dataclass
class IngestionRun:
    """Mutable record of one run; the ingestion code fills in the counts."""

    run_id: uuid.UUID
    source_id: str
    status: str = "success"
    rows_extracted: int = 0
    rows_loaded: int = 0
    rows_rejected: int = 0
    source_release: str | None = None
    source_checksum: str | None = None


_START_SQL = text(
    "INSERT INTO audit.ingestion_runs (run_id, source_id, status) "
    "VALUES (:run_id, :source_id, 'running')"
)

_FINISH_SQL = text(
    """
    UPDATE audit.ingestion_runs
    SET status           = :status,
        finished_at      = now(),
        duration_seconds = :duration_seconds,
        rows_extracted   = :rows_extracted,
        rows_loaded      = :rows_loaded,
        rows_rejected    = :rows_rejected,
        source_release   = :source_release,
        source_checksum  = :source_checksum,
        error_message    = :error_message
    WHERE run_id = :run_id
    """
)


def _finish(
    engine: Engine, run: IngestionRun, status: str, duration: float, error: str | None
) -> None:
    with engine.begin() as conn:
        conn.execute(
            _FINISH_SQL,
            {
                "run_id": run.run_id,
                "status": status,
                "duration_seconds": round(duration, 3),
                "rows_extracted": run.rows_extracted,
                "rows_loaded": run.rows_loaded,
                "rows_rejected": run.rows_rejected,
                "source_release": run.source_release,
                "source_checksum": run.source_checksum,
                "error_message": error,
            },
        )


@contextmanager
def track_ingestion_run(engine: Engine, source_id: str) -> Iterator[IngestionRun]:
    """Context manager that records the start, outcome and timing of a run."""
    run = IngestionRun(run_id=uuid.uuid4(), source_id=source_id)

    # Recorded in its OWN transaction, committed immediately: if the load
    # later fails and rolls back, the audit record of the attempt survives.
    with engine.begin() as conn:
        conn.execute(_START_SQL, {"run_id": run.run_id, "source_id": source_id})
    logger.info("Run %s started for source '%s'", run.run_id, source_id)

    started = time.perf_counter()
    try:
        yield run
    except Exception as exc:
        duration = time.perf_counter() - started
        message = f"{type(exc).__name__}: {exc}"[:MAX_ERROR_LENGTH]
        _finish(engine, run, "failed", duration, message)
        logger.exception("Run %s FAILED for '%s' after %.1fs", run.run_id, source_id, duration)
        raise
    else:
        duration = time.perf_counter() - started
        if run.status not in FINAL_STATUSES:
            raise ValueError(f"Invalid final status '{run.status}'")
        _finish(engine, run, run.status, duration, None)
        logger.info(
            "Run %s %s for '%s': extracted=%d loaded=%d rejected=%d in %.1fs",
            run.run_id,
            run.status.upper(),
            source_id,
            run.rows_extracted,
            run.rows_loaded,
            run.rows_rejected,
            duration,
        )


def release_already_loaded(engine: Engine, source_id: str, release: str) -> bool:
    """True if a previous run of `source_id` successfully loaded `release`.

    Used for release-based incremental loading: if the source has not
    published anything new since the last successful run, skip it.
    """
    query = text(
        "SELECT EXISTS (SELECT 1 FROM audit.ingestion_runs "
        "WHERE source_id = :source_id AND source_release = :release AND status = 'success')"
    )
    with engine.connect() as conn:
        return conn.execute(query, {"source_id": source_id, "release": release}).scalar_one()


def checksum_already_loaded(engine: Engine, source_id: str, checksum: str) -> bool:
    """True if a previous run of `source_id` successfully loaded a file with this checksum."""
    query = text(
        "SELECT EXISTS (SELECT 1 FROM audit.ingestion_runs "
        "WHERE source_id = :source_id AND source_checksum = :checksum AND status = 'success')"
    )
    with engine.connect() as conn:
        return conn.execute(query, {"source_id": source_id, "checksum": checksum}).scalar_one()