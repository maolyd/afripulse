"""Failure scenario: a bad batch is blocked before it reaches the warehouse.

Simulates the World Bank suddenly returning far too few rows plus an aggregate
code. The run must fail, nothing may be loaded, and every check result must be
stored in audit.validation_results for investigation.
"""

from unittest.mock import Mock

import pytest
from sqlalchemy import text

from afripulse.db.connection import get_engine
from afripulse.ingestion.jobs import run_worldbank_wdi
from afripulse.validation.checks import DataValidationError

pytestmark = pytest.mark.integration

TABLE = "raw.test_validation_values"
SOURCE_ID = "test_validation_wdi"
SOURCE = {
    "base_url": "https://api.worldbank.org/v2",
    "page_size": 1000,
    "start_year": 2024,
    "raw_table": TABLE,
    "natural_key": ["indicator_code", "country_iso3", "year"],
    "indicators": [{"code": "SP.POP.TOTL"}],
    "validation": {
        "min_records": 3,
        "country_field": "country_iso3",
        "min_countries": 3,
        "value_field": ["payload", "value"],
        "max_null_pct": 10,
    },
}


def fake_client(rows):
    client = Mock()
    client.get_json.return_value = [{"pages": 1, "lastupdated": "2026-10-08"}, rows]
    return client


def row(iso3, value):
    return {"countryiso3code": iso3, "date": "2024", "value": value}


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


def latest_run(engine):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT run_id, status, error_message FROM audit.ingestion_runs "
                "WHERE source_id = :s ORDER BY started_at DESC LIMIT 1"
            ),
            {"s": SOURCE_ID},
        ).one()


def checks(engine, run_id):
    with engine.connect() as conn:
        return dict(
            conn.execute(
                text("SELECT check_name, passed FROM audit.validation_results WHERE run_id = :r"),
                {"r": run_id},
            ).all()
        )


def test_bad_batch_is_blocked_and_results_are_recorded(engine):
    bad_rows = [row("KEN", 56_400_000), row("AFE", 750_000_000)]  # too few + an aggregate

    with pytest.raises(DataValidationError, match="nothing loaded"):
        run_worldbank_wdi(
            engine, fake_client(bad_rows), SOURCE_ID, SOURCE, country_codes=["KEN", "NGA", "GHA"]
        )

    run_id, status, error = latest_run(engine)
    assert status == "failed"
    assert "min_records" in error or "minimum 3" in error
    results = checks(engine, run_id)
    assert results["min_records"] is False
    assert results["country_codes_valid"] is False
    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT count(*) FROM {TABLE}")).scalar_one() == 0


def test_warnings_are_recorded_but_do_not_block_the_load(engine):
    rows = [row("KEN", 1), row("NGA", None), row("GHA", 3)]  # 33% null > 10% limit

    run_worldbank_wdi(
        engine, fake_client(rows), SOURCE_ID, SOURCE, country_codes=["KEN", "NGA", "GHA"]
    )

    run_id, status, _ = latest_run(engine)
    assert status == "success"
    assert checks(engine, run_id)["null_rate"] is False
    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT count(*) FROM {TABLE}")).scalar_one() == 3
