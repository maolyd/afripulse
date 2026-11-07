"""Pre-load validation: check extracted records BEFORE they reach the database.

Each check returns a CheckResult. Severity decides what happens:

    error    the load is blocked and the run fails: loading would put wrong data
             in the warehouse (too few rows, unknown country codes, impossible years)
    warning  the load continues and the problem is recorded: worth a look, but the
             data may still be valid (a higher null rate, fewer countries than usual)

Rules come from the `validation:` block of each source in config/sources.yml,
so every threshold is visible, reviewable and backed by a discovery finding.
"""

import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from afripulse.ingestion.base import Record

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckResult:
    check_name: str
    severity: str  # "error" or "warning"
    passed: bool
    message: str
    observed: float | None = None
    threshold: float | None = None


@dataclass
class ValidationReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def failed_errors(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and r.severity == "error"]

    @property
    def failed_warnings(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and r.severity == "warning"]

    def summary(self) -> str:
        return (
            "; ".join(r.message for r in self.failed_errors + self.failed_warnings) or "all passed"
        )


class DataValidationError(ValueError):
    """At least one error-level check failed: the batch must not be loaded."""


def get_field(record: Record, path: str | Sequence[str]) -> Any:
    """Read a value from a record. `path` is a key, or a list of keys into nested dicts.

    A list is needed because some source columns contain dots (e.g. "account.t.d").
    """
    keys = [path] if isinstance(path, str) else list(path)
    value: Any = record
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


# --------------------------------------------------------------------- checks


def check_min_records(records: Sequence[Record], minimum: int) -> CheckResult:
    count = len(records)
    return CheckResult(
        "min_records",
        "error",
        count >= minimum,
        f"{count} records (minimum {minimum})",
        count,
        minimum,
    )


def check_duplicate_keys(records: Sequence[Record], key_columns: Sequence[str]) -> CheckResult:
    counts = Counter(tuple(record.get(column) for column in key_columns) for record in records)
    duplicates = [key for key, n in counts.items() if n > 1]
    return CheckResult(
        "duplicate_keys",
        "error",
        not duplicates,
        f"{len(duplicates)} duplicate key(s)" + (f", e.g. {duplicates[:3]}" if duplicates else ""),
        len(duplicates),
        0,
    )


def check_country_codes(
    records: Sequence[Record], country_field: str | Sequence[str], allowed: set[str]
) -> CheckResult:
    found = {get_field(record, country_field) for record in records}
    invalid = sorted(str(code) for code in found - allowed)
    return CheckResult(
        "country_codes_valid",
        "error",
        not invalid,
        f"{len(invalid)} country code(s) not in reference list"
        + (f": {invalid[:10]}" if invalid else ""),
        len(invalid),
        0,
    )


def check_country_coverage(
    records: Sequence[Record], country_field: str | Sequence[str], minimum: int
) -> CheckResult:
    countries = len({get_field(record, country_field) for record in records})
    return CheckResult(
        "country_coverage",
        "warning",
        countries >= minimum,
        f"{countries} countries present (expected at least {minimum})",
        countries,
        minimum,
    )


def check_year_range(
    records: Sequence[Record], year_field: str | Sequence[str], low: int, high: int
) -> CheckResult:
    years = [get_field(record, year_field) for record in records]
    outside = sorted({y for y in years if not isinstance(y, int) or not low <= y <= high}, key=str)
    return CheckResult(
        "year_range",
        "error",
        not outside,
        f"{len(outside)} year value(s) outside {low}-{high}"
        + (f": {outside[:10]}" if outside else ""),
        len(outside),
        0,
    )


def check_null_rates(
    records: Sequence[Record],
    value_field: str | Sequence[str],
    max_pct: float,
    group_by: str | None = None,
    overrides: dict[str, float] | None = None,
) -> list[CheckResult]:
    """Share of records with a null value, overall or per group (e.g. per indicator)."""
    overrides = overrides or {}
    totals: Counter = Counter()
    nulls: Counter = Counter()
    for record in records:
        group = record.get(group_by) if group_by else "all"
        totals[group] += 1
        if get_field(record, value_field) is None:
            nulls[group] += 1

    results = []
    for group in sorted(totals, key=str):
        pct = 100 * nulls[group] / totals[group]
        limit = overrides.get(group, max_pct)
        name = f"null_rate:{group}" if group_by else "null_rate"
        results.append(
            CheckResult(
                name,
                "warning",
                pct <= limit,
                f"{group}: {pct:.1f}% null (limit {limit}%)",
                round(pct, 2),
                limit,
            )
        )
    return results


def check_row_count_change(current: int, previous: int | None, max_drop_pct: float) -> CheckResult:
    """Compare with the previous successful run: a sudden drop often means a broken source."""
    if not previous:
        return CheckResult("row_count_change", "warning", True, "no previous run to compare with")
    change_pct = round(100 * (current - previous) / previous, 2)
    return CheckResult(
        "row_count_change",
        "warning",
        change_pct >= -max_drop_pct,
        f"{current} records vs {previous} last run ({change_pct:+.1f}%, max drop {max_drop_pct}%)",
        change_pct,
        -max_drop_pct,
    )


# ------------------------------------------------------------------- runner


def validate_records(
    records: Sequence[Record],
    rules: dict[str, Any],
    key_columns: Sequence[str],
    reference_countries: set[str],
    previous_count: int | None = None,
) -> ValidationReport:
    """Run every check that `rules` asks for. Duplicate keys are always checked."""
    report = ValidationReport()
    add = report.results.append

    add(check_duplicate_keys(records, key_columns))
    if "min_records" in rules:
        add(check_min_records(records, int(rules["min_records"])))
    if "country_field" in rules:
        add(check_country_codes(records, rules["country_field"], reference_countries))
        if "min_countries" in rules:
            add(
                check_country_coverage(records, rules["country_field"], int(rules["min_countries"]))
            )
    if "year_field" in rules and "year_range" in rules:
        low, high = rules["year_range"]
        add(check_year_range(records, rules["year_field"], int(low), int(high)))
    if "value_field" in rules:
        report.results.extend(
            check_null_rates(
                records,
                rules["value_field"],
                float(rules.get("max_null_pct", 100)),
                rules.get("group_by"),
                {str(k): float(v) for k, v in rules.get("max_null_pct_overrides", {}).items()},
            )
        )
    if "max_drop_pct" in rules:
        add(check_row_count_change(len(records), previous_count, float(rules["max_drop_pct"])))

    for result in report.failed_errors:
        logger.error("Validation ERROR %s: %s", result.check_name, result.message)
    for result in report.failed_warnings:
        logger.warning("Validation warning %s: %s", result.check_name, result.message)
    logger.info(
        "Validation: %d checks, %d error(s), %d warning(s)",
        len(report.results),
        len(report.failed_errors),
        len(report.failed_warnings),
    )
    return report
