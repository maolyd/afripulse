"""Integration test: every reporting table exports to a labelled CSV."""

import csv

import pytest

from afripulse.db.connection import get_engine
from afripulse.reporting.export import EXTRACTS, export_all

pytestmark = pytest.mark.integration


@pytest.fixture
def engine():
    eng = get_engine()
    yield eng
    eng.dispose()


def test_every_extract_is_written_with_header_and_label(engine, tmp_path):
    counts = export_all(engine, export_dir=tmp_path)

    assert set(counts) == {e.file_name for e in EXTRACTS}
    for extract in EXTRACTS:
        with (tmp_path / extract.file_name).open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            first = next(reader, None)
            rows = 1 + sum(1 for _ in reader) if first else 0
        assert rows == counts[extract.file_name]
        if first:
            expected = "SYNTHETIC" if extract.file_name.startswith("SYNTHETIC") else "REAL"
            assert first["data_label"] == expected
    assert (tmp_path / "MANIFEST.md").is_file()


def test_booleans_are_written_as_true_false_for_tableau(engine, tmp_path):
    export_all(engine, export_dir=tmp_path)

    with (tmp_path / "SYNTHETIC_loyalty_customers.csv").open(encoding="utf-8") as handle:
        row = next(csv.DictReader(handle), None)
    if row is None:
        pytest.skip("no loyalty members in this warehouse")
    assert row["has_mobile_money"] in {"true", "false"}
    assert row["never_redeemed"] in {"true", "false"}
