"""Integration test: build a report from the real database and save it."""

import pytest
from sqlalchemy import text

from afripulse.db.connection import get_engine
from afripulse.quality.report import build_report, save_report

pytestmark = pytest.mark.integration


@pytest.fixture
def engine():
    eng = get_engine()
    yield eng
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM audit.dq_reports WHERE report_path LIKE '%pytest%'"))
    eng.dispose()


def test_report_is_built_saved_and_recorded(engine, tmp_path):
    report = build_report(engine)
    path = save_report(engine, report, report_dir=tmp_path / "pytest_reports")

    assert report.status in {"GREEN", "AMBER", "RED"}
    assert path.is_file()
    assert (
        (path.parent / "latest.md")
        .read_text(encoding="utf-8")
        .startswith("# AfriPulse Data Quality Report")
    )
    with engine.connect() as conn:
        stored = conn.execute(
            text("SELECT status FROM audit.dq_reports WHERE report_path = :p"), {"p": str(path)}
        ).scalar_one()
    assert stored == report.status
