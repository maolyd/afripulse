"""Export the dbt reporting layer to CSV files for Tableau Public.

Tableau Public runs in the browser and cannot reach a database on a laptop, so
dashboards are built from extracts. Each `reporting.rpt_*` table is written to
exports/tableau/ with PostgreSQL COPY (fast, exact), and SYNTHETIC files say so
in their name. A MANIFEST.md lists every file, its rows and what it is for.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, text

from afripulse.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

EXPORT_DIR = PROJECT_ROOT / "exports" / "tableau"


@dataclass(frozen=True)
class Extract:
    table: str  # in the reporting schema
    file_name: str
    purpose: str


EXTRACTS = [
    Extract(
        "rpt_country_year",
        "real_country_year.csv",
        "Dashboards 1-4: every indicator per country and year (actuals, default source)",
    ),
    Extract(
        "rpt_indicator_sources",
        "real_indicator_sources.csv",
        "Dashboard 2: source comparison (IMF vs World Bank) and projections",
    ),
    Extract(
        "rpt_synthetic_mobile_money",
        "SYNTHETIC_mobile_money_transactions.csv",
        "Dashboard 4: mobile money transactions",
    ),
    Extract(
        "rpt_synthetic_retail_transactions",
        "SYNTHETIC_retail_transactions.csv",
        "Dashboard 5: retail purchases",
    ),
    Extract(
        "rpt_synthetic_loyalty_customers",
        "SYNTHETIC_loyalty_customers.csv",
        "Dashboard 6: loyalty members",
    ),
]


def select_list(engine: Engine, table: str) -> str:
    """Columns of a reporting table, with booleans written as true/false.

    PostgreSQL's CSV output writes booleans as t/f, which Tableau reads as text;
    true/false is recognised as a boolean (filters become simple switches).
    """
    query = text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'reporting' AND table_name = :table ORDER BY ordinal_position"
    )
    with engine.connect() as conn:
        columns = conn.execute(query, {"table": table}).all()
    if not columns:
        raise ValueError(f"reporting.{table} not found: run `make dbt-build` first")
    return ", ".join(
        f"CASE WHEN {name} THEN 'true' WHEN NOT {name} THEN 'false' END AS {name}"
        if data_type == "boolean"
        else name
        for name, data_type in columns
    )


def export_extract(engine: Engine, extract: Extract, export_dir: Path) -> int:
    """Write one reporting table to CSV. Returns the number of data rows."""
    path = export_dir / extract.file_name
    columns = select_list(engine, extract.table)
    copy_sql = (
        f"COPY (SELECT {columns} FROM reporting.{extract.table}) "
        "TO STDOUT WITH (FORMAT csv, HEADER)"
    )
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT count(*) FROM reporting.{extract.table}")).scalar_one()
        cursor = conn.connection.driver_connection.cursor()
        with (
            path.open("wb") as handle,
            cursor.copy(copy_sql) as copy,
        ):
            for chunk in copy:
                handle.write(chunk)
    logger.info("Exported %s rows to %s", f"{rows:,}", path)
    return rows


def export_all(engine: Engine, export_dir: Path = EXPORT_DIR) -> dict[str, int]:
    export_dir.mkdir(parents=True, exist_ok=True)
    counts = {e.file_name: export_extract(engine, e, export_dir) for e in EXTRACTS}

    lines = [
        "# AfriPulse extracts for Tableau Public",
        "",
        f"Exported {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by `make export-tableau`.",
        "Files starting with SYNTHETIC hold generated data calibrated to real statistics;",
        "they never describe real people, merchants or transactions.",
        "",
        "| File | Rows | Size | Purpose |",
        "|---|---:|---:|---|",
    ]
    for e in EXTRACTS:
        size_mb = (export_dir / e.file_name).stat().st_size / 1_000_000
        lines.append(
            f"| {e.file_name} | {counts[e.file_name]:,} | {size_mb:.1f} MB | {e.purpose} |"
        )
    (export_dir / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts
