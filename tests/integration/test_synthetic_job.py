"""End-to-end synthetic job: generate, check invariants, COPY into PostgreSQL, skip on rerun.

Writes into throwaway copies (raw_synthetic.test_*) so the real synthetic
tables are never touched.
"""

from pathlib import Path

import pytest
from sqlalchemy import text

from afripulse.db.connection import get_engine
from afripulse.ingestion.jobs import run_synthetic
from afripulse.synthetic.load import SYNTHETIC_TABLES
from afripulse.synthetic.settings import load_synthetic_settings

pytestmark = pytest.mark.integration

PREFIX = "test_"
SOURCE_ID = "test_synthetic"
SMALL_SETTINGS = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_small.yml"


@pytest.fixture
def engine():
    eng = get_engine()
    with eng.begin() as conn:
        for table in SYNTHETIC_TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS raw_synthetic.{PREFIX}{table}"))
            conn.execute(
                text(
                    f"CREATE TABLE raw_synthetic.{PREFIX}{table} "
                    f"(LIKE raw_synthetic.{table} INCLUDING ALL)"
                )
            )
    yield eng
    with eng.begin() as conn:
        for table in SYNTHETIC_TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS raw_synthetic.{PREFIX}{table}"))
        conn.execute(
            text("DELETE FROM audit.ingestion_runs WHERE source_id = :s"), {"s": SOURCE_ID}
        )
    eng.dispose()


def run(engine, settings, force=False):
    run_synthetic(engine, None, SOURCE_ID, settings, force=force, table_prefix=PREFIX)


def counts(engine):
    with engine.connect() as conn:
        return {
            t: conn.execute(text(f"SELECT count(*) FROM raw_synthetic.{PREFIX}{t}")).scalar_one()
            for t in SYNTHETIC_TABLES
        }


def test_generates_loads_and_skips_unchanged_inputs(engine):
    settings = load_synthetic_settings(SMALL_SETTINGS)
    run(engine, settings)
    first = counts(engine)
    run(engine, settings)  # same inputs: skipped

    with engine.connect() as conn:
        statuses = (
            conn.execute(
                text(
                    "SELECT status FROM audit.ingestion_runs "
                    "WHERE source_id = :s ORDER BY started_at"
                ),
                {"s": SOURCE_ID},
            )
            .scalars()
            .all()
        )
        flags = conn.execute(
            text(f"SELECT bool_and(is_synthetic) FROM raw_synthetic.{PREFIX}retail_transactions")
        ).scalar_one()

    assert statuses == ["success", "skipped"]
    assert first["customers"] == 400
    assert first["retail_transactions"] > 0 and first["loyalty_events"] > 0
    assert flags is True  # every row is labelled synthetic


def test_rerun_replaces_instead_of_duplicating(engine):
    settings = load_synthetic_settings(SMALL_SETTINGS)
    run(engine, settings)
    first = counts(engine)
    run(engine, settings, force=True)

    assert counts(engine) == first  # regenerated identically, not appended
