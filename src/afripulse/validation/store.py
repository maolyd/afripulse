"""Persist validation results and read the history they are compared against."""

import uuid

from sqlalchemy import Engine, text

from afripulse.validation.checks import ValidationReport

_INSERT_SQL = text(
    """
    INSERT INTO audit.validation_results
        (run_id, check_name, severity, passed, observed, threshold, message)
    VALUES (:run_id, :check_name, :severity, :passed, :observed, :threshold, :message)
    """
)


def save_validation_report(engine: Engine, run_id: uuid.UUID, report: ValidationReport) -> None:
    """Write every check result, in its own transaction, so it survives a failed load."""
    if not report.results:
        return
    rows = [
        {
            "run_id": run_id,
            "check_name": r.check_name,
            "severity": r.severity,
            "passed": r.passed,
            "observed": r.observed,
            "threshold": r.threshold,
            "message": r.message,
        }
        for r in report.results
    ]
    with engine.begin() as conn:
        conn.execute(_INSERT_SQL, rows)


def previous_row_count(engine: Engine, source_id: str, current_run_id: uuid.UUID) -> int | None:
    """rows_extracted of the most recent earlier successful run, if any."""
    query = text(
        """
        SELECT rows_extracted FROM audit.ingestion_runs
        WHERE source_id = :source_id AND status = 'success' AND run_id <> :run_id
        ORDER BY started_at DESC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        return conn.execute(query, {"source_id": source_id, "run_id": current_run_id}).scalar()
