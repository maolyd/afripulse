"""End-to-end test of a World Bank ingestion job against the real database.

The network is faked (recorded-style responses), but everything else is real:
the job, the loader, the raw table and the audit table. Test data goes into a
throwaway table and is removed afterwards, so real raw tables are untouched.
"""

from unittest.mock import Mock

import pytest
from sqlalchemy import text

from afripulse.db.connection import get_engine
from afripulse.ingestion.jobs import run_worldbank_wdi

pytestmark = pytest.mark.integration

TABLE = "raw.test_worldbank_values"
SOURCE_ID = "test_worldbank_wdi"
SOURCE = {
    "base_url": "https://api.worldbank.org/v2",
    "page_size": 1000,
    "start_year": 2024,
    "raw_table": TABLE,
    "natural_key": ["indicator_code", "country_iso3", "year"],
    "indicators": [{"code": "SP.POP.TOTL"}],
}


def fake_client():
    rows = [
        {"countryiso3code": iso3, "date": "2024", "value": value}
        for iso3, value in [("KEN", 56_400_000), ("NGA", 232_700_000)]
    ]
    client = Mock()
    client.get_json.return_value = [{"pages": 1, "lastupdated": "2026-10-08"}, rows]
    return client


@pytest.fixture
def engine():
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))
        conn.execute(
            text(f"CREATE TABLE {TABLE} (LIKE raw.worldbank_indicator_values INCLUDING ALL)")
        )
    yield eng
    with eng.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))
        conn.execute(
            text("DELETE FROM audit.ingestion_runs WHERE source_id = :s"), {"s": SOURCE_ID}
        )
    eng.dispose()


def audit_rows(engine):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT status, rows_extracted, rows_loaded, source_release "
                "FROM audit.ingestion_runs WHERE source_id = :s ORDER BY started_at"
            ),
            {"s": SOURCE_ID},
        ).all()


def test_running_the_job_twice_is_idempotent_and_audited(engine):
    for _ in range(2):
        run_worldbank_wdi(engine, fake_client(), SOURCE_ID, SOURCE, country_codes=["KEN", "NGA"])

    with engine.connect() as conn:
        rows, batches = conn.execute(
            text(f"SELECT count(*), count(DISTINCT _batch_id) FROM {TABLE}")
        ).one()
    assert rows == 2  # no duplicates after two runs
    assert batches == 1  # second run rewrote nothing

    first, second = audit_rows(engine)
    assert first == ("success", 2, 2, "2026-10-08")
    assert second == ("success", 2, 0, "2026-10-08")  # extracted again, nothing new to load


def test_a_failing_extraction_is_audited_as_failed(engine):
    client = Mock()
    client.get_json.side_effect = RuntimeError("API is down")

    with pytest.raises(RuntimeError):
        run_worldbank_wdi(engine, client, SOURCE_ID, SOURCE, country_codes=["KEN"])

    assert audit_rows(engine)[-1][0] == "failed"
