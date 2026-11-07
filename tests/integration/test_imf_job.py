"""End-to-end test of the IMF job: release-based incremental loading.

Network faked, database real. Uses a throwaway table and test source id.
"""

from unittest.mock import Mock

import pytest
from sqlalchemy import text

from afripulse.db.connection import get_engine
from afripulse.ingestion.jobs import run_imf_weo

pytestmark = pytest.mark.integration

TABLE = "raw.test_imf_values"
SOURCE_ID = "test_imf_weo"
SOURCE = {
    "base_url": "https://www.imf.org/external/datamapper/api/v1",
    "raw_table": TABLE,
    "natural_key": ["release", "indicator_code", "area_code", "year"],
    "indicators": [{"code": "NGDP_RPCH"}],
}


def fake_client(release_label="World Economic Outlook (October 2026)"):
    def get_json(url, params=None):
        if url.endswith("/indicators"):
            return {"indicators": {"NGDP_RPCH": {"source": release_label}}}
        return {"values": {"NGDP_RPCH": {"KEN": {"2025": 4.6, "2026": 4.5}, "AFQ": {"2025": 4}}}}

    client = Mock()
    client.get_json.side_effect = get_json
    return client


@pytest.fixture
def engine():
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))
        conn.execute(text(f"CREATE TABLE {TABLE} (LIKE raw.imf_weo_values INCLUDING ALL)"))
    yield eng
    with eng.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))
        conn.execute(
            text("DELETE FROM audit.ingestion_runs WHERE source_id = :s"), {"s": SOURCE_ID}
        )
    eng.dispose()


def runs(engine):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT status, rows_loaded, source_release FROM audit.ingestion_runs "
                "WHERE source_id = :s ORDER BY started_at"
            ),
            {"s": SOURCE_ID},
        ).all()


def run(engine, force=False, **client_kwargs):
    run_imf_weo(
        engine, fake_client(**client_kwargs), SOURCE_ID, SOURCE, country_codes=["KEN"], force=force
    )


def test_same_release_is_skipped_on_the_second_run(engine):
    run(engine)
    run(engine)

    assert runs(engine) == [
        ("success", 2, "WEO-2026-10"),
        ("skipped", 0, "WEO-2026-10"),
    ]


def test_force_reloads_but_the_loader_writes_nothing_new(engine):
    run(engine)
    run(engine, force=True)

    assert runs(engine)[-1] == ("success", 0, "WEO-2026-10")


def test_a_new_release_is_loaded_alongside_the_old_one(engine):
    run(engine)
    run(engine, release_label="World Economic Outlook (April 2027)")

    with engine.connect() as conn:
        releases = conn.execute(
            text(f"SELECT release, count(*) FROM {TABLE} GROUP BY 1 ORDER BY 1")
        ).all()
    assert releases == [("WEO-2026-10", 2), ("WEO-2027-04", 2)]  # history kept (F-IMF-3)
