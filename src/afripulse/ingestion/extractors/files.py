"""Extract rows from downloaded CSV and Excel files.

One generic extractor serves every file source. What differs between sources
lives in config/sources.yml, not in code:

    read_options     how to read the file (sheet, header row, rows to skip)
    country_column   column holding the ISO3 code, used to keep only countries in scope
    key_columns      raw key column -> source column, e.g. {year: Time}
    integer_keys     key columns that must be whole numbers

So adding a new file source means adding configuration and a raw table, not code.

Findings applied: every value is read as TEXT with pandas' automatic
"NA"-to-null conversion switched off (F-UN-3: Namibia), and only empty cells
become null.
"""

import hashlib
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from afripulse.ingestion.base import ExtractResult, Record

logger = logging.getLogger(__name__)

EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}


class SourceFileMissingError(FileNotFoundError):
    """A manually downloaded file is not in the landing zone."""


def file_checksum(path: Path) -> str:
    """SHA-256 of the file, read in 1 MB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_source_file(path: Path, read_options: dict[str, Any]) -> pd.DataFrame:
    """Read a CSV or Excel file with every value as text."""
    common = {"dtype": str, "keep_default_na": False, "na_values": [""]}
    if path.suffix.lower() in EXCEL_SUFFIXES:
        return pd.read_excel(
            path,
            sheet_name=read_options.get("sheet_name", 0),
            header=read_options.get("header_row", 0),
            skiprows=read_options.get("skip_rows"),
            **common,
        )
    return pd.read_csv(path, low_memory=False, **common)


class FileExtractor:
    def __init__(self, path: Path, source: dict[str, Any], download_hint: str = "") -> None:
        self.path = path
        self.source = source
        if not path.is_file():
            raise SourceFileMissingError(
                f"{path} not found. Download it manually{download_hint} "
                "and place it in the landing folder."
            )

    def checksum(self) -> str:
        return file_checksum(self.path)

    def extract(self, country_codes: Sequence[str], release: str) -> ExtractResult:
        df = read_source_file(self.path, self.source.get("read_options", {}))
        country_column = self.source["country_column"]
        key_columns: dict[str, str] = self.source["key_columns"]
        integer_keys = set(self.source.get("integer_keys", []))

        missing = [c for c in [country_column, *key_columns.values()] if c not in df.columns]
        if missing:
            raise ValueError(f"{self.path.name}: expected columns not found: {missing}")

        in_scope = set(country_codes)
        codes = df[country_column].fillna("").str.strip().str.upper()
        df = df[codes.isin(in_scope)]
        logger.info("%s: %d rows read, %d in scope", self.path.name, len(codes), len(df))

        url = f"file:{self.source['landing_path']}"
        result = ExtractResult(source_release=release)
        for row in df.to_dict(orient="records"):
            record = self._record(row, key_columns, integer_keys, release, url)
            if record is None:
                result.rows_rejected += 1
            else:
                result.records.append(record)
        return result

    @staticmethod
    def _record(
        row: dict[str, Any],
        key_columns: dict[str, str],
        integer_keys: set[str],
        release: str,
        url: str,
    ) -> Record | None:
        payload = {str(k): (None if pd.isna(v) else v) for k, v in row.items()}
        record: Record = {"release": release, "payload": payload, "_source_url": url}
        for raw_column, source_column in key_columns.items():
            value = payload.get(source_column)
            if value is None:
                logger.warning("Rejected row: empty key %s (%s)", source_column, raw_column)
                return None
            value = str(value).strip()
            if raw_column in integer_keys:
                if not value.isdigit():
                    logger.warning(
                        "Rejected row: %s=%r is not a whole number", source_column, value
                    )
                    return None
                record[raw_column] = int(value)
            else:
                record[raw_column] = value
        return record
