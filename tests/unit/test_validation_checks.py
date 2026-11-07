"""Unit tests for the pre-load validation checks (pure Python, no database)."""

import pytest

from afripulse.validation.checks import (
    check_country_codes,
    check_country_coverage,
    check_duplicate_keys,
    check_min_records,
    check_null_rates,
    check_row_count_change,
    check_year_range,
    get_field,
    validate_records,
)

REFERENCE = {"KEN", "NGA", "GHA"}


def record(iso3="KEN", year=2024, value=1.0, indicator="SP.POP.TOTL"):
    return {
        "indicator_code": indicator,
        "country_iso3": iso3,
        "year": year,
        "payload": {"value": value, "account.t.d": value},
    }


def test_get_field_reads_nested_keys_including_dotted_names():
    rec = record(value=0.9)

    assert get_field(rec, "country_iso3") == "KEN"
    assert get_field(rec, ["payload", "account.t.d"]) == 0.9
    assert get_field(rec, ["payload", "missing", "deeper"]) is None


def test_min_records():
    assert check_min_records([record()] * 3, 3).passed
    failed = check_min_records([record()] * 2, 3)
    assert not failed.passed and failed.severity == "error"


def test_duplicate_keys_are_an_error():
    result = check_duplicate_keys([record(), record()], ["country_iso3", "year"])

    assert not result.passed
    assert result.severity == "error"
    assert result.observed == 1


def test_unknown_country_codes_are_an_error():
    """Aggregates such as 'AFE' (Africa Eastern and Southern) must never be loaded as countries."""
    result = check_country_codes([record("KEN"), record("AFE")], "country_iso3", REFERENCE)

    assert not result.passed
    assert "AFE" in result.message


def test_low_country_coverage_is_only_a_warning():
    result = check_country_coverage([record("KEN")], "country_iso3", minimum=3)

    assert not result.passed
    assert result.severity == "warning"


def test_year_range_rejects_impossible_and_non_integer_years():
    result = check_year_range(
        [record(year=2024), record(year=1899), record(year="2024")], "year", 1950, 2030
    )

    assert not result.passed
    assert result.observed == 2


def test_null_rates_per_group_with_override():
    """F7: Findex-based indicators are mostly null by design, so they get their own limit."""
    records = [record(value=None, indicator="FX.OWN.TOTL.ZS")] * 9 + [
        record(value=1, indicator="FX.OWN.TOTL.ZS")
    ]
    records += [record(value=None)] + [record(value=1)] * 9

    results = check_null_rates(
        records,
        ["payload", "value"],
        max_pct=35,
        group_by="indicator_code",
        overrides={"FX.OWN.TOTL.ZS": 95},
    )

    by_name = {r.check_name: r for r in results}
    assert by_name["null_rate:FX.OWN.TOTL.ZS"].passed  # 90% <= 95%
    assert by_name["null_rate:SP.POP.TOTL"].passed  # 10% <= 35%


def test_null_rate_above_limit_is_a_warning():
    (result,) = check_null_rates([record(value=None)] * 5, ["payload", "value"], max_pct=10)

    assert not result.passed and result.severity == "warning"
    assert result.observed == 100


@pytest.mark.parametrize(
    ("current", "previous", "passes"),
    [(100, None, True), (100, 100, True), (95, 100, True), (50, 100, False), (150, 100, True)],
)
def test_row_count_change(current, previous, passes):
    assert check_row_count_change(current, previous, max_drop_pct=10).passed is passes


def test_unchanged_row_count_reads_as_plus_zero():
    assert "+0.0%" in check_row_count_change(100, 100, max_drop_pct=10).message


def test_validate_records_runs_only_configured_checks():
    rules = {"min_records": 1, "country_field": "country_iso3", "min_countries": 1}

    report = validate_records([record()], rules, ["country_iso3", "year"], REFERENCE)

    names = {r.check_name for r in report.results}
    assert names == {"duplicate_keys", "min_records", "country_codes_valid", "country_coverage"}
    assert report.failed_errors == []


def test_report_separates_errors_from_warnings():
    rules = {"min_records": 5, "country_field": "country_iso3", "min_countries": 3}

    report = validate_records([record()], rules, ["country_iso3", "year"], REFERENCE)

    assert [r.check_name for r in report.failed_errors] == ["min_records"]
    assert [r.check_name for r in report.failed_warnings] == ["country_coverage"]
    assert "minimum 5" in report.summary()
