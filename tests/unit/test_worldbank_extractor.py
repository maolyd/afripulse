"""Unit tests for the World Bank extractor, using recorded-style responses.

The fake responses below copy the real API's shape, as seen in Task 2.1:
[metadata, records], ISO2 in country.id, ISO3 in countryiso3code, years as text.
"""

from unittest.mock import Mock

import pytest

from afripulse.ingestion.extractors.worldbank import WorldBankAPIError, WorldBankExtractor

BASE_URL = "https://api.worldbank.org/v2"


def page(rows, page_number=1, pages=1, lastupdated="2026-10-08"):
    meta = {"page": page_number, "pages": pages, "total": len(rows), "lastupdated": lastupdated}
    return [meta, rows]


def indicator_row(iso3, year, value, code="SP.POP.TOTL"):
    return {
        "indicator": {"id": code, "value": "Population, total"},
        "country": {"id": iso3[:2], "value": iso3},
        "countryiso3code": iso3,
        "date": str(year),
        "value": value,
        "unit": "",
        "obs_status": "",
        "decimal": 0,
    }


def make_extractor(*responses):
    client = Mock()
    client.get_json.side_effect = list(responses)
    return WorldBankExtractor(client, BASE_URL, page_size=2), client


def test_follows_pagination_until_the_last_page():
    extractor, client = make_extractor(
        page([indicator_row("KEN", 2024, 1), indicator_row("KEN", 2025, 2)], 1, 2),
        page([indicator_row("NGA", 2024, 3)], 2, 2),
    )

    result = extractor.extract_indicators(["SP.POP.TOTL"], ["KEN", "NGA"], 2024, 2025)

    assert len(result.records) == 3
    assert [call.args[1]["page"] for call in client.get_json.call_args_list] == [1, 2]


def test_request_uses_country_list_and_year_range():
    extractor, client = make_extractor(page([]))

    extractor.extract_indicators(["IT.NET.USER.ZS"], ["KEN", "NGA"], 2000, 2025)

    url, params = client.get_json.call_args.args
    assert url == f"{BASE_URL}/country/KEN;NGA/indicator/IT.NET.USER.ZS"
    assert params["date"] == "2000:2025"
    assert params["format"] == "json"


def test_records_use_iso3_integer_year_and_keep_the_original_payload():
    row = indicator_row("AGO", 2025, 39040039)
    extractor, _ = make_extractor(page([row]))

    record = extractor.extract_indicators(["SP.POP.TOTL"], ["AGO"], 2025, 2025).records[0]

    assert record["country_iso3"] == "AGO"  # not the ISO2 "AG" from country.id (F4)
    assert record["year"] == 2025  # integer, not "2025" (F6)
    assert record["payload"] == row  # untouched original
    assert record["_source_release"] == "2026-10-08"  # lastupdated (F12)


def test_null_values_are_kept():
    extractor, _ = make_extractor(page([indicator_row("ERI", 2024, None)]))

    result = extractor.extract_indicators(["NY.GDP.PCAP.CD"], ["ERI"], 2024, 2024)

    assert len(result.records) == 1  # F11: nulls kept in raw
    assert result.records[0]["payload"]["value"] is None


def test_rows_without_a_valid_iso3_or_year_are_rejected():
    bad_iso3 = indicator_row("KEN", 2024, 1) | {"countryiso3code": ""}
    bad_year = indicator_row("KEN", 2024, 1) | {"date": "2024Q1"}
    extractor, _ = make_extractor(page([bad_iso3, bad_year, indicator_row("KEN", 2025, 2)]))

    result = extractor.extract_indicators(["SP.POP.TOTL"], ["KEN"], 2024, 2025)

    assert len(result.records) == 1
    assert result.rows_rejected == 2


def test_error_message_with_http_200_raises():
    """F13: the API reports some errors as a successful response."""
    error = [{"message": [{"id": "120", "key": "Invalid value", "value": "bad indicator"}]}]
    extractor, _ = make_extractor(error)

    with pytest.raises(WorldBankAPIError, match="Invalid value"):
        extractor.extract_indicators(["NOT.A.CODE"], ["KEN"], 2024, 2024)


def test_countries_keep_aggregates_for_raw_storage():
    kenya = {"id": "KEN", "region": {"value": "Sub-Saharan Africa "}}
    africa = {"id": "AFR", "region": {"value": "Aggregates"}}
    extractor, _ = make_extractor(page([kenya, africa]))

    result = extractor.extract_countries()

    assert [record["country_code"] for record in result.records] == ["KEN", "AFR"]
