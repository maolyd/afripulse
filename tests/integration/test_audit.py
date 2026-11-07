"""Integration tests for audit tracking against the real database."""

import pytest
from sqlalchemy import text

from afripulse.db.audit import track_ingestion_run
from afripulse.db.connection import get_engine

pytestmark = pytest.mark.integration

TEST_SOURCE = "test_audit_source"


@pytest.fixture(scope="module")
def engine():
    eng = get_engine()
    yield eng
    with eng.begin() as conn:  # clean up rows created by these tests
        conn.execute(
            text("DELETE FROM audit.ingestion_runs WHERE source_id = :s"), {"s": TEST_SOURCE}
        )
    eng.dispose()


def fetch_run(engine, run_id) -> dict:
    with engine.connect() as conn:
        row = (
            conn.execute(
                text("SELECT * FROM audit.ingestion_runs WHERE run_id = :id"), {"id": run_id}
            )
            .mappings()
            .one()
        )
    return dict(row)


def test_successful_run_is_recorded(engine):
    with track_ingestion_run(engine, TEST_SOURCE) as run:
        run.rows_extracted = 10
        run.rows_loaded = 8
        run.rows_rejected = 2

    row = fetch_run(engine, run.run_id)
    assert row["status"] == "success"
    assert (row["rows_extracted"], row["rows_loaded"], row["rows_rejected"]) == (10, 8, 2)
    assert row["finished_at"] is not None
    assert row["duration_seconds"] >= 0


def test_failed_run_is_recorded_and_error_is_reraised(engine):
    with pytest.raises(RuntimeError, match="simulated failure"):
        with track_ingestion_run(engine, TEST_SOURCE) as run:
            raise RuntimeError("simulated failure")

    row = fetch_run(engine, run.run_id)
    assert row["status"] == "failed"
    assert "RuntimeError: simulated failure" in row["error_message"]
