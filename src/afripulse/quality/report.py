"""Data quality report: every check in one place, with one overall status.

Gathers the results that already exist across the platform:

    1. Ingestion      audit.ingestion_runs      latest run per source, recent failures
    2. Validation     audit.validation_results  pre-load checks of each source's latest load
    3. dbt tests      target/run_results.json   the last `dbt build`
    4. Freshness      target/sources.json       the last `dbt source freshness`
    5. Coverage       marts                     countries with data, synthetic labelling

and turns them into issues of two severities:

    RED    something is wrong with the data or the pipeline: act now
    AMBER  worth a look, but the data can still be used

Overall status: RED if any red issue, else AMBER if any amber issue, else GREEN.
The report is saved as Markdown (reports/data_quality/) and summarised in
audit.dq_reports, so data quality can be tracked over time.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, text

from afripulse.config import PROJECT_ROOT
from afripulse.sources_config import load_sources_config

logger = logging.getLogger(__name__)

DBT_TARGET = PROJECT_ROOT / "dbt" / "afripulse" / "target"
REPORT_DIR = PROJECT_ROOT / "reports" / "data_quality"
EXPECTED_SOURCES = [*load_sources_config()["sources"], "synthetic"]
RECENT_DAYS = 7
MIN_COUNTRY_COVERAGE = 45  # of 54: below this, Africa-wide figures are unreliable (F15)


@dataclass(frozen=True)
class Issue:
    severity: str  # "RED" or "AMBER"
    area: str
    message: str


@dataclass
class Report:
    generated_at: datetime
    issues: list[Issue] = field(default_factory=list)
    sections: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        severities = {issue.severity for issue in self.issues}
        return "RED" if "RED" in severities else "AMBER" if "AMBER" in severities else "GREEN"

    def count(self, severity: str) -> int:
        return sum(issue.severity == severity for issue in self.issues)

    def add(self, severity: str, area: str, message: str) -> None:
        self.issues.append(Issue(severity, area, message))


# ------------------------------------------------------------------ gathering


def check_ingestion(engine: Engine, report: Report) -> None:
    latest_sql = text(
        """
        SELECT DISTINCT ON (source_id)
               source_id, status, started_at, rows_extracted, rows_loaded,
               rows_rejected, duration_seconds, source_release, error_message
        FROM audit.ingestion_runs
        WHERE source_id = ANY(:sources)
        ORDER BY source_id, started_at DESC
        """
    )
    failures_sql = text(
        """
        SELECT source_id, count(*) FROM audit.ingestion_runs
        WHERE status = 'failed' AND source_id = ANY(:sources)
          AND started_at > now() - make_interval(days => :days)
        GROUP BY source_id
        """
    )
    with engine.connect() as conn:
        latest = [
            dict(r) for r in conn.execute(latest_sql, {"sources": EXPECTED_SOURCES}).mappings()
        ]
        recent_failures = dict(
            conn.execute(failures_sql, {"sources": EXPECTED_SOURCES, "days": RECENT_DAYS}).all()
        )

    seen = {run["source_id"] for run in latest}
    for source_id in sorted(set(EXPECTED_SOURCES) - seen):
        report.add("RED", "ingestion", f"{source_id}: has never been ingested")
    for run in latest:
        if run["status"] == "failed":
            error = (run["error_message"] or "")[:160]
            report.add("RED", "ingestion", f"{run['source_id']}: latest run FAILED: {error}")
        elif recent_failures.get(run["source_id"]):
            n = recent_failures[run["source_id"]]
            report.add(
                "AMBER",
                "ingestion",
                f"{run['source_id']}: {n} failed run(s) in the last {RECENT_DAYS} days "
                "(latest run recovered)",
            )
    report.sections["ingestion"] = latest


def check_validation(engine: Engine, report: Report) -> None:
    """Failed pre-load checks from each source's most recent validated run."""
    sql = text(
        """
        WITH latest_validated AS (
            SELECT DISTINCT ON (r.source_id) r.source_id, r.run_id
            FROM audit.ingestion_runs r
            WHERE EXISTS (SELECT 1 FROM audit.validation_results v WHERE v.run_id = r.run_id)
              AND r.source_id = ANY(:sources)
            ORDER BY r.source_id, r.started_at DESC
        )
        SELECT l.source_id, v.check_name, v.severity, v.passed, v.message
        FROM latest_validated l
        JOIN audit.validation_results v USING (run_id)
        ORDER BY l.source_id, v.check_name
        """
    )
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(sql, {"sources": EXPECTED_SOURCES}).mappings()]

    for row in rows:
        if not row["passed"]:
            severity = "RED" if row["severity"] == "error" else "AMBER"
            report.add(severity, "validation", f"{row['source_id']}: {row['message']}")
    report.sections["validation"] = {
        "checks": len(rows),
        "failed": sum(not r["passed"] for r in rows),
    }


def check_dbt_results(report: Report, target_dir: Path = DBT_TARGET) -> None:
    path = target_dir / "run_results.json"
    if not path.is_file():
        report.add("RED", "dbt", "no dbt results found: run `make dbt-build`")
        return
    results = json.loads(path.read_text(encoding="utf-8"))
    command = results.get("args", {}).get("which")
    if command != "build":
        report.add(
            "AMBER",
            "dbt",
            f"last dbt command was `{command}`, not `build`: test results may be out of date",
        )

    counts: dict[str, int] = {}
    for result in results["results"]:
        status = result["status"]
        counts[status] = counts.get(status, 0) + 1
        name = result["unique_id"].split(".")[-1]
        if status in ("fail", "error"):
            report.add(
                "RED", "dbt", f"{name}: {status} ({result.get('failures') or result['message']})"
            )
        elif status == "warn":
            report.add("AMBER", "dbt", f"{name}: warning ({result.get('failures')})")
    report.sections["dbt"] = {
        "command": command,
        "generated_at": results["metadata"]["generated_at"],
        "counts": counts,
    }


def check_freshness(report: Report, target_dir: Path = DBT_TARGET) -> None:
    path = target_dir / "sources.json"
    if not path.is_file():
        report.add("AMBER", "freshness", "no freshness results: run `make dbt-freshness`")
        return
    results = json.loads(path.read_text(encoding="utf-8"))["results"]
    rows = []
    for result in results:
        name = result["unique_id"].removeprefix("source.afripulse.")
        age_days = (result.get("max_loaded_at_time_ago_in_s") or 0) / 86400
        rows.append({"source": name, "status": result["status"], "age_days": round(age_days, 1)})
        if result["status"] in ("error", "runtime error"):
            report.add("RED", "freshness", f"{name}: stale ({age_days:.0f} days since last load)")
        elif result["status"] == "warn":
            report.add("AMBER", "freshness", f"{name}: getting stale ({age_days:.0f} days)")
    report.sections["freshness"] = rows


def check_coverage(engine: Engine, report: Report) -> None:
    """Countries with data in the latest year of each digital adoption measure (F15)."""
    measures = ["internet_users_pct", "mobile_subscriptions_per_100", "mobile_money_account_pct"]
    rows = []
    with engine.connect() as conn:
        for measure in measures:  # fixed list above: safe to put in the SQL text
            year, countries = conn.execute(
                text(
                    f"""
                    SELECT year, count({measure}) FROM marts.fact_digital_adoption
                    WHERE year = (SELECT max(year) FROM marts.fact_digital_adoption
                                  WHERE {measure} IS NOT NULL)
                    GROUP BY year
                    """
                )
            ).one_or_none() or (None, 0)
            rows.append({"measure": measure, "latest_year": year, "countries": countries})
            # Findex covers fewer countries by design (F-FX-6): 37 African countries
            # have a 2024 mobile money value. A warning that always fires gets ignored.
            minimum = 35 if measure == "mobile_money_account_pct" else MIN_COUNTRY_COVERAGE
            if countries < minimum:
                report.add(
                    "AMBER",
                    "coverage",
                    f"{measure}: only {countries} of 54 countries in {year} "
                    f"(Africa-wide averages may be biased, F15)",
                )
        unlabelled = conn.execute(
            text(
                "SELECT count(*) FROM marts.fact_retail_transactions WHERE is_synthetic IS NOT TRUE"
            )
        ).scalar_one()
    if unlabelled:
        report.add("RED", "coverage", f"{unlabelled} transaction rows are not labelled synthetic")
    report.sections["coverage"] = rows


def build_report(engine: Engine, target_dir: Path = DBT_TARGET) -> Report:
    report = Report(generated_at=datetime.now(UTC))
    for name, check in [
        ("ingestion", lambda: check_ingestion(engine, report)),
        ("validation", lambda: check_validation(engine, report)),
        ("dbt", lambda: check_dbt_results(report, target_dir)),
        ("freshness", lambda: check_freshness(report, target_dir)),
        ("coverage", lambda: check_coverage(engine, report)),
    ]:
        try:
            check()
        except Exception as error:  # one broken check must not hide the others
            logger.exception("Data quality check '%s' could not run", name)
            report.add("RED", name, f"check could not run: {type(error).__name__}: {error}")
    return report


# ------------------------------------------------------------------ output

STATUS_ICON = {"GREEN": "🟢", "AMBER": "🟠", "RED": "🔴"}


def render_markdown(report: Report) -> str:
    lines = [
        "# AfriPulse Data Quality Report",
        "",
        f"**Status: {STATUS_ICON[report.status]} {report.status}**  ",
        f"Generated: {report.generated_at:%Y-%m-%d %H:%M UTC}  ",
        f"Issues: {report.count('RED')} red, {report.count('AMBER')} amber",
        "",
        "## Issues",
        "",
    ]
    if report.issues:
        lines += ["| Severity | Area | Issue |", "|---|---|---|"]
        for issue in sorted(report.issues, key=lambda i: (i.severity != "RED", i.area)):
            icon = STATUS_ICON[issue.severity]
            lines.append(f"| {icon} {issue.severity} | {issue.area} | {issue.message} |")
    else:
        lines.append("None: every check passed.")

    ingestion = report.sections.get("ingestion", [])
    lines += ["", "## 1. Ingestion (latest run per source)", ""]
    lines += [
        "| Source | Status | Started (UTC) | Extracted | Loaded | Rejected | Seconds | Release |"
    ]
    lines += ["|---|---|---|---:|---:|---:|---:|---|"]
    for run in ingestion:
        lines.append(
            f"| {run['source_id']} | {run['status']} | {run['started_at']:%Y-%m-%d %H:%M} | "
            f"{run['rows_extracted'] or 0:,} | {run['rows_loaded'] or 0:,} | "
            f"{run['rows_rejected'] or 0:,} | {run['duration_seconds'] or 0} | "
            f"{run['source_release'] or ''} |"
        )

    validation = report.sections.get("validation", {})
    lines += ["", "## 2. Pre-load validation", ""]
    lines.append(
        f"{validation.get('checks', 0)} checks on each source's latest load, "
        f"{validation.get('failed', 0)} failed."
    )

    dbt = report.sections.get("dbt")
    lines += ["", "## 3. dbt build and tests", ""]
    if dbt:
        counts = ", ".join(f"{k}: {v}" for k, v in sorted(dbt["counts"].items()))
        lines.append(f"Last `dbt {dbt['command']}` at {dbt['generated_at'][:16]}: {counts}.")

    lines += ["", "## 4. Source freshness", "", "| Source | Status | Days since last load |"]
    lines += ["|---|---|---:|"]
    for row in report.sections.get("freshness", []):
        lines.append(f"| {row['source']} | {row['status']} | {row['age_days']} |")

    lines += ["", "## 5. Coverage (countries with data, latest year)", ""]
    lines += ["| Measure | Latest year | Countries (of 54) |", "|---|---|---:|"]
    for row in report.sections.get("coverage", []):
        lines.append(f"| {row['measure']} | {row['latest_year']} | {row['countries']} |")
    lines += ["", "_Transaction-level data in AfriPulse is SYNTHETIC._", ""]
    return "\n".join(lines)


def save_report(engine: Engine, report: Report, report_dir: Path = REPORT_DIR) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(report)
    path = report_dir / f"dq_report_{report.generated_at:%Y%m%d_%H%M%S}.md"
    path.write_text(markdown, encoding="utf-8")
    (report_dir / "latest.md").write_text(markdown, encoding="utf-8")

    summary = {
        "issues": [issue.__dict__ for issue in report.issues],
        "dbt": report.sections.get("dbt"),
        "validation": report.sections.get("validation"),
        "coverage": report.sections.get("coverage"),
    }
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO audit.dq_reports (report_id, generated_at, status,
                    red_issues, amber_issues, summary, report_path)
                VALUES (:id, :at, :status, :red, :amber, CAST(:summary AS jsonb), :path)
                """
            ),
            {
                "id": uuid.uuid4(),
                "at": report.generated_at,
                "status": report.status,
                "red": report.count("RED"),
                "amber": report.count("AMBER"),
                "summary": json.dumps(summary, default=str),
                "path": str(path.relative_to(PROJECT_ROOT))
                if path.is_relative_to(PROJECT_ROOT)
                else str(path),
            },
        )
    logger.info(
        "Data quality: %s (%d red, %d amber) -> %s",
        report.status,
        report.count("RED"),
        report.count("AMBER"),
        path,
    )
    return path
