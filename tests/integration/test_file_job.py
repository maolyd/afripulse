"""End-to-end test of a file-source job: checksum-based incremental loading."""

import pytest
from sqlalchemy import text

from afripulse.config import PROJECT_ROOT
from afripulse.db.connection import get_engine
from afripulse.ingestion.jobs import run_file_source

pytestmark = pytest.mark.integration

TABLE = "raw.test_file_values"
SOURCE_ID = "test_file_source"
LANDING = PROJECT_ROOT / "data" / "landing" / "test_file_job.csv"
SOURCE = {
    "landing_path": "data/landing/test_file_job.csv",
    "release": "TEST2026",
    "country_column": "ISO3_code",
    "key_columns": {"loc_id": "LocID", "year": "Time"},
    "integer_keys": ["loc_id", "year"],
    "raw_table": TABLE,
    "natural_key": ["release", "loc_id", "year"],
}


def write_file(kenya_population: str) -> None:
    LANDING.write_text(
        "LocID,ISO3_code,Time,TPopulation1July\n"
        f"404,KEN,2025,{kenya_population}\n"
        "566,NGA,2025,237528.0\n"
        "903,,2025,1549000.0\n",
        encoding="utf-8",
    )


@pytest.fixture
def engine():
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))
        conn.execute(
            text(f"CREATE TABLE {TABLE} (LIKE raw.un_wpp_demographic_indicators INCLUDING ALL)")
        )
    yield eng
    LANDING.unlink(missing_ok=True)
    with eng.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))
        conn.execute(
            text("DELETE FROM audit.ingestion_runs WHERE source_id = :s"), {"s": SOURCE_ID}
        )
    eng.dispose()


def run(engine, force=False):
    run_file_source(engine, None, SOURCE_ID, SOURCE, country_codes=["KEN", "NGA"], force=force)


def runs(engine):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT status, rows_loaded FROM audit.ingestion_runs "
                "WHERE source_id = :s ORDER BY started_at"
            ),
            {"s": SOURCE_ID},
        ).all()


def test_unchanged_file_is_skipped_and_changed_file_is_reloaded(engine):
    write_file("57532.5")
    run(engine)  # first load
    run(engine)  # same file: skipped
    write_file("57600.0")  # a revised value
    run(engine)  # changed file: loaded again

    assert runs(engine) == [("success", 2), ("skipped", 0), ("success", 1)]


def test_force_reloads_an_unchanged_file(engine):
    write_file("57532.5")
    run(engine)
    run(engine, force=True)

    assert runs(engine)[-1] == ("success", 0)  # read again, loader found nothing new
