"""Unit tests for the data quality report (no database: dbt result files are faked)."""

import json
from datetime import UTC, datetime

import pytest

from afripulse.quality.report import (
    Report,
    check_dbt_results,
    check_freshness,
    render_markdown,
)


def new_report() -> Report:
    return Report(generated_at=datetime(2026, 11, 8, 5, 45, tzinfo=UTC))


def write_run_results(target, results, which="build"):
    target.mkdir(parents=True, exist_ok=True)
    (target / "run_results.json").write_text(
        json.dumps(
            {
                "metadata": {"generated_at": "2026-11-08T05:40:00Z"},
                "args": {"which": which},
                "results": results,
            }
        )
    )


def result(name, status, failures=None, message=""):
    return {
        "unique_id": f"test.afripulse.{name}",
        "status": status,
        "failures": failures,
        "message": message,
    }


@pytest.mark.parametrize(
    ("severities", "expected"),
    [([], "GREEN"), (["AMBER"], "AMBER"), (["AMBER", "RED"], "RED"), (["RED"], "RED")],
)
def test_overall_status_is_the_worst_issue(severities, expected):
    report = new_report()
    for severity in severities:
        report.add(severity, "test", "x")

    assert report.status == expected


def test_passing_dbt_build_raises_no_issue(tmp_path):
    write_run_results(tmp_path, [result("unique_x", "pass"), result("model_y", "success")])
    report = new_report()

    check_dbt_results(report, tmp_path)

    assert report.issues == []
    assert report.sections["dbt"]["counts"] == {"pass": 1, "success": 1}


def test_failed_dbt_test_is_red_and_named(tmp_path):
    write_run_results(tmp_path, [result("assert_loyalty_balances_reconcile", "fail", 97)])
    report = new_report()

    check_dbt_results(report, tmp_path)

    assert report.status == "RED"
    assert "assert_loyalty_balances_reconcile: fail (97)" in report.issues[0].message


def test_results_from_another_dbt_command_are_flagged(tmp_path):
    write_run_results(tmp_path, [result("x", "success")], which="docs")
    report = new_report()

    check_dbt_results(report, tmp_path)

    assert report.status == "AMBER"
    assert "not `build`" in report.issues[0].message


def test_missing_dbt_results_are_red(tmp_path):
    report = new_report()

    check_dbt_results(report, tmp_path)

    assert report.status == "RED"


def test_stale_source_is_red_and_warning_is_amber(tmp_path):
    (tmp_path / "sources.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "unique_id": "source.afripulse.raw.imf_weo_values",
                        "status": "error",
                        "max_loaded_at_time_ago_in_s": 40 * 86400,
                    },
                    {
                        "unique_id": "source.afripulse.raw.findex_values",
                        "status": "warn",
                        "max_loaded_at_time_ago_in_s": 9 * 86400,
                    },
                ]
            }
        )
    )
    report = new_report()

    check_freshness(report, tmp_path)

    assert [i.severity for i in report.issues] == ["RED", "AMBER"]
    assert "raw.imf_weo_values: stale (40 days" in report.issues[0].message


def test_markdown_shows_status_and_every_issue():
    report = new_report()
    report.add("RED", "ingestion", "imf_weo: latest run FAILED")
    report.add("AMBER", "coverage", "internet_users_pct: only 40 of 54 countries")

    markdown = render_markdown(report)

    assert "Status: 🔴 RED" in markdown
    assert "imf_weo: latest run FAILED" in markdown
    assert "only 40 of 54 countries" in markdown
    assert "SYNTHETIC" in markdown
