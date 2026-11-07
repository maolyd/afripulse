"""Integration tests: the loader is idempotent against a real PostgreSQL table."""

import uuid

import pytest
from sqlalchemy import text

from afripulse.db.connection import get_engine
from afripulse.db.loader import DuplicateKeyError, upsert_records

pytestmark = pytest.mark.integration

TABLE = "raw.test_loader_values"


@pytest.fixture
def engine():
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))
        conn.execute(
            text(
                f"""
                CREATE TABLE {TABLE} (
                    country_iso3 text NOT NULL,
                    year integer NOT NULL,
                    payload jsonb NOT NULL,
                    _record_hash text NOT NULL,
                    _source_url text NOT NULL,
                    _source_release text,
                    _batch_id uuid NOT NULL,
                    _ingested_at timestamptz NOT NULL DEFAULT now(),
                    PRIMARY KEY (country_iso3, year)
                )
                """
            )
        )
    yield eng
    with eng.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))
    eng.dispose()


def make_records(kenya_value: float = 5.7) -> list[dict]:
    rows = [("KEN", 2023, kenya_value), ("NGA", 2023, 2.9), ("GHA", 2023, 3.1)]
    return [
        {
            "country_iso3": iso3,
            "year": year,
            "payload": {"country": iso3, "date": str(year), "value": value},
            "_source_url": "https://example.org/test",
        }
        for iso3, year, value in rows
    ]


def load(engine, records):
    return upsert_records(engine, TABLE, ["country_iso3", "year"], records, uuid.uuid4())


def row_count(engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {TABLE}")).scalar_one()


def test_first_load_inserts_everything(engine):
    result = load(engine, make_records())

    assert (result.inserted, result.updated, result.unchanged) == (3, 0, 0)
    assert row_count(engine) == 3


def test_second_identical_load_changes_nothing(engine):
    load(engine, make_records())
    result = load(engine, make_records())

    assert (result.inserted, result.updated, result.unchanged) == (0, 0, 3)
    assert row_count(engine) == 3  # idempotent: no duplicates


def test_revised_value_updates_only_that_row(engine):
    load(engine, make_records(kenya_value=5.7))
    result = load(engine, make_records(kenya_value=5.6))

    assert (result.inserted, result.updated, result.unchanged) == (0, 1, 2)
    with engine.connect() as conn:
        value = conn.execute(
            text(f"SELECT payload->>'value' FROM {TABLE} WHERE country_iso3 = 'KEN'")
        ).scalar_one()
    assert value == "5.6"


def test_duplicate_keys_in_one_batch_are_rejected_and_nothing_is_written(engine):
    records = make_records() + make_records()[:1]

    with pytest.raises(DuplicateKeyError):
        load(engine, records)
    assert row_count(engine) == 0
