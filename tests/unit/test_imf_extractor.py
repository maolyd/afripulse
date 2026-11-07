"""Unit tests for the IMF extractor, using responses shaped like the real API (Task 2.2)."""

from unittest.mock import Mock

import pytest

from afripulse.ingestion.extractors.imf import IMFAPIError, IMFExtractor, parse_release

BASE_URL = "https://www.imf.org/external/datamapper/api/v1"
OCTOBER = "World Economic Outlook (October 2026)"


def catalogue(**sources):
    return {"indicators": {code: {"label": code, "source": src} for code, src in sources.items()}}


def series(code, values):
    return {"values": {code: values}, "api": {"version": "1"}}


def make_extractor(*responses):
    client = Mock()
    client.get_json.side_effect = list(responses)
    return IMFExtractor(client, BASE_URL), client


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("World Economic Outlook (October 2026)", "WEO-2026-10"),
        ("World Economic Outlook (April 2027)", "WEO-2027-04"),
    ],
)
def test_parse_release(label, expected):
    assert parse_release(label) == expected


@pytest.mark.parametrize("label", ["", "Some other source", "World Economic Outlook (Spring 2026)"])
def test_parse_release_rejects_unknown_labels(label):
    with pytest.raises(IMFAPIError):
        parse_release(label)


def test_detect_release_reads_the_api_catalogue():
    extractor, _ = make_extractor(catalogue(NGDP_RPCH=OCTOBER, PCPIPCH=OCTOBER))

    assert extractor.detect_release(["NGDP_RPCH", "PCPIPCH"]) == "WEO-2026-10"


def test_detect_release_fails_for_an_unknown_indicator():
    extractor, _ = make_extractor(catalogue(NGDP_RPCH=OCTOBER))

    with pytest.raises(IMFAPIError, match="NOT_REAL"):
        extractor.detect_release(["NGDP_RPCH", "NOT_REAL"])


def test_detect_release_fails_if_indicators_come_from_different_releases():
    extractor, _ = make_extractor(
        catalogue(NGDP_RPCH=OCTOBER, PCPIPCH="World Economic Outlook (April 2026)")
    )

    with pytest.raises(IMFAPIError, match="different releases"):
        extractor.detect_release(["NGDP_RPCH", "PCPIPCH"])


def test_extract_keeps_only_reference_countries():
    """F-IMF-4: aggregates (AFQ, ADVEC) and non-African countries are dropped."""
    values = {
        "KEN": {"2025": 4.6, "2031": 5},
        "AFQ": {"2025": 4.0},
        "ADVEC": {"2025": 1.5},
        "USA": {"2025": 2.0},
    }
    extractor, _ = make_extractor(series("NGDP_RPCH", values))

    result = extractor.extract(["NGDP_RPCH"], ["KEN", "NGA"], "WEO-2026-10")

    assert {record["area_code"] for record in result.records} == {"KEN"}
    assert len(result.records) == 2  # actual 2025 and projection 2031 both kept


def test_extract_builds_records_with_release_integer_year_and_payload():
    extractor, _ = make_extractor(series("PCPIPCH", {"KEN": {"2025": 4.1}}))

    record = extractor.extract(["PCPIPCH"], ["KEN"], "WEO-2026-10").records[0]

    assert record["release"] == "WEO-2026-10"
    assert record["year"] == 2025
    assert record["payload"] == {
        "indicator": "PCPIPCH",
        "area": "KEN",
        "year": "2025",
        "value": 4.1,
    }
    assert record["_source_url"] == f"{BASE_URL}/PCPIPCH"


def test_extract_skips_null_values_and_rejects_bad_years():
    values = {"KEN": {"2024": None, "2025": 4.6, "2025-26": 4.7}}
    extractor, _ = make_extractor(series("NGDP_RPCH", values))

    result = extractor.extract(["NGDP_RPCH"], ["KEN"], "WEO-2026-10")

    assert [record["year"] for record in result.records] == [2025]
    assert result.rows_rejected == 1


def test_extract_fails_when_the_indicator_has_no_values():
    extractor, _ = make_extractor({"values": {}})

    with pytest.raises(IMFAPIError, match="NGDP_RPCH"):
        extractor.extract(["NGDP_RPCH"], ["KEN"], "WEO-2026-10")
