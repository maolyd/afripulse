"""Unit tests for the generic file extractor, using small files built per test."""

import pandas as pd
import pytest

from afripulse.ingestion.extractors.files import (
    FileExtractor,
    SourceFileMissingError,
    file_checksum,
)

WPP_SOURCE = {
    "landing_path": "data/landing/manual/un_wpp/test.csv",
    "country_column": "ISO3_code",
    "key_columns": {"loc_id": "LocID", "year": "Time"},
    "integer_keys": ["loc_id", "year"],
}


@pytest.fixture
def wpp_csv(tmp_path):
    path = tmp_path / "wpp.csv"
    path.write_text(
        "LocID,ISO3_code,ISO2_code,Location,Time,TPopulation1July,Notes\n"
        "516,NAM,NA,Namibia,2025,3092.5,\n"
        "404,KEN,KE,Kenya,2025,57532.5,\n"
        "903,,,Africa,2025,1549000.0,\n"
        "840,USA,US,United States,2025,347276.0,\n",
        encoding="utf-8",
    )
    return path


def test_missing_file_gives_a_clear_message(tmp_path):
    with pytest.raises(SourceFileMissingError, match="Download it manually from https://x"):
        FileExtractor(tmp_path / "absent.csv", WPP_SOURCE, " from https://x")


def test_only_countries_in_scope_are_kept(wpp_csv):
    """F-UN-4: aggregates (no ISO3) and non-African countries are dropped."""
    result = FileExtractor(wpp_csv, WPP_SOURCE).extract(["KEN", "NAM"], "WPP2024")

    assert sorted(record["payload"]["ISO3_code"] for record in result.records) == ["KEN", "NAM"]


def test_namibia_iso2_survives_and_empty_cells_become_null(wpp_csv):
    """F-UN-3: 'NA' must stay text; only truly empty cells are null."""
    result = FileExtractor(wpp_csv, WPP_SOURCE).extract(["NAM"], "WPP2024")
    payload = result.records[0]["payload"]

    assert payload["ISO2_code"] == "NA"
    assert payload["Notes"] is None


def test_values_are_kept_as_text_exactly_as_in_the_file(wpp_csv):
    """F-UN-1: units are converted in staging, never in raw."""
    payload = FileExtractor(wpp_csv, WPP_SOURCE).extract(["KEN"], "WPP2024").records[0]["payload"]

    assert payload["TPopulation1July"] == "57532.5"  # thousands, as published


def test_key_columns_are_mapped_and_typed(wpp_csv):
    record = FileExtractor(wpp_csv, WPP_SOURCE).extract(["KEN"], "WPP2024").records[0]

    assert (record["release"], record["loc_id"], record["year"]) == ("WPP2024", 404, 2025)
    assert record["_source_url"] == "file:data/landing/manual/un_wpp/test.csv"


def test_rows_with_invalid_keys_are_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("LocID,ISO3_code,Time\n404,KEN,2025\n404,KEN,2025-26\n,KEN,2024\n")

    result = FileExtractor(path, WPP_SOURCE).extract(["KEN"], "WPP2024")

    assert len(result.records) == 1
    assert result.rows_rejected == 2


def test_missing_expected_columns_fail_loudly(tmp_path):
    path = tmp_path / "renamed.csv"
    path.write_text("LocationID,ISO3_code,Year\n404,KEN,2025\n")

    with pytest.raises(ValueError, match="expected columns not found"):
        FileExtractor(path, WPP_SOURCE).extract(["KEN"], "WPP2024")


def test_excel_with_notes_sheet_and_second_header_row(tmp_path):
    """F-FX-1 and F-FX-2: data on the 2nd sheet, labels in the 2nd header row."""
    path = tmp_path / "findex.xlsx"
    data = pd.DataFrame(
        [
            ["Economy code", "Year", "Demographic group", "Demographic sub-group", "Account (%)"],
            ["KEN", 2024, "all", "all", 0.901],
            ["KEN", 2024, "gender", "women", 0.88],
        ],
        columns=["codewb", "year", "group", "group2", "account.t.d"],
    )
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"NOTES": ["Read me first"]}).to_excel(writer, sheet_name="Notes", index=False)
        data.to_excel(writer, sheet_name="Data", index=False)
    source = {
        "landing_path": "findex.xlsx",
        "read_options": {"sheet_name": "Data", "header_row": 0, "skip_rows": [1]},
        "country_column": "codewb",
        "key_columns": {
            "codewb": "codewb",
            "year": "year",
            "demographic_group": "group",
            "demographic_subgroup": "group2",
        },
        "integer_keys": ["year"],
    }

    result = FileExtractor(path, source).extract(["KEN"], "FINDEX2025")

    assert [r["demographic_subgroup"] for r in result.records] == ["all", "women"]
    assert result.records[0]["year"] == 2024
    assert result.records[0]["payload"]["account.t.d"] == "0.901"


def test_checksum_changes_when_content_changes(tmp_path):
    path = tmp_path / "file.csv"
    path.write_text("a,b\n1,2\n")
    before = file_checksum(path)
    path.write_text("a,b\n1,3\n")

    assert file_checksum(path) != before
    assert len(before) == 64
