"""Load the synthetic dataset into raw_synthetic with PostgreSQL COPY.

COPY streams rows straight into a table and is much faster than INSERT for
hundreds of thousands of rows. Synthetic data is fully regenerated each run,
so loading REPLACES the previous version, all in one transaction: readers see
either the old dataset or the new one, never a mix.
"""

import logging
import uuid

import pandas as pd
from sqlalchemy import Engine

from afripulse.synthetic.calibration import Calibration
from afripulse.synthetic.generators import SyntheticDataset

logger = logging.getLogger(__name__)

SCHEMA = "raw_synthetic"
SYNTHETIC_TABLES = (
    "calibration",
    "customers",
    "merchants",
    "retail_transactions",
    "mobile_money_transactions",
    "loyalty_events",
)


def _python_rows(df: pd.DataFrame) -> list[tuple]:
    """Convert numpy/pandas values (and NaN/None) into plain Python values for COPY."""
    clean = df.astype(object).where(df.notna(), None)
    return [tuple(row) for row in clean.itertuples(index=False, name=None)]


def _copy(cursor, table: str, df: pd.DataFrame) -> None:
    columns = ", ".join(df.columns)
    with cursor.copy(f"COPY {table} ({columns}) FROM STDIN") as copy:
        for row in _python_rows(df):
            copy.write_row(row)


def calibration_frame(calibration: Calibration, run_id: uuid.UUID) -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            {
                "country_iso3": v.country_iso3,
                "metric": v.metric,
                "value": v.value,
                "source": v.source,
                "source_year": v.source_year,
                "generator_run_id": run_id,
            }
            for metrics in calibration.values()
            for v in metrics.values()
        ]
    )
    # A column with some missing years would become float (2024.0), which an
    # integer column rejects. "Int64" is pandas' integer type that allows nulls.
    frame["source_year"] = frame["source_year"].astype("Int64")
    return frame


def replace_synthetic_data(
    engine: Engine,
    data: SyntheticDataset,
    calibration: Calibration,
    run_id: uuid.UUID,
    table_prefix: str = "",
) -> int:
    """Replace every raw_synthetic table with `data`.

    Returns the number of synthetic rows written (calibration rows not counted).
    `table_prefix` exists for tests, so they never touch the real tables.
    """
    tables = {"calibration": calibration_frame(calibration, run_id)}
    for name, df in data.tables().items():
        tables[name] = df.assign(generator_run_id=run_id)

    def name(table: str) -> str:
        return f"{SCHEMA}.{table_prefix}{table}"

    written = 0
    with engine.begin() as conn:
        cursor = conn.connection.driver_connection.cursor()
        # One statement for all tables: PostgreSQL refuses to truncate a table that
        # another table references, unless both are truncated together. Listing
        # them explicitly (instead of CASCADE) guarantees nothing else is emptied.
        cursor.execute("TRUNCATE " + ", ".join(name(t) for t in SYNTHETIC_TABLES))
        for table in SYNTHETIC_TABLES:  # parents before children
            _copy(cursor, name(table), tables[table])
            logger.info("Copied %d rows into %s", len(tables[table]), name(table))
            if table != "calibration":
                written += len(tables[table])
    return written
