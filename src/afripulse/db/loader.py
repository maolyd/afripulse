"""Idempotent loading of records into raw tables.

Every raw table has the same shape: natural key columns + the standard
metadata columns below. Loading uses an "upsert":

  * key not in the table yet          -> INSERT          (counted as inserted)
  * key present, payload has changed  -> UPDATE          (counted as updated)
  * key present, payload identical    -> leave untouched (counted as unchanged)

So running the same load twice changes nothing the second time: the load is
IDEMPOTENT. A changed value (e.g. a revised GDP figure) replaces the old one,
and its _record_hash, _batch_id and _ingested_at show when that happened.
"""

import hashlib
import json
import logging
import re
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)

METADATA_COLUMNS = ("payload", "_record_hash", "_source_url", "_source_release", "_batch_id")

# Table and column names cannot be passed as bind parameters, so they are put
# into the SQL text. Only allow plain lower-case names, to make SQL injection
# through a config file impossible.
_IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]*")


class DuplicateKeyError(ValueError):
    """The same natural key appears more than once in one batch."""


@dataclass(frozen=True)
class LoadResult:
    received: int
    inserted: int
    updated: int

    @property
    def unchanged(self) -> int:
        return self.received - self.inserted - self.updated

    @property
    def loaded(self) -> int:
        """Rows actually written (new or changed)."""
        return self.inserted + self.updated


def record_hash(payload: Any) -> str:
    """Stable SHA-256 of a payload: key order and whitespace do not matter."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_identifier(name: str) -> str:
    """Return `name` if it is a safe SQL identifier (optionally schema.table)."""
    parts = name.split(".")
    if len(parts) > 2 or not all(_IDENTIFIER.fullmatch(part) for part in parts):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name


def find_duplicate_keys(
    records: Sequence[dict[str, Any]], key_columns: Sequence[str]
) -> list[tuple]:
    counts = Counter(tuple(record[column] for column in key_columns) for record in records)
    return [key for key, count in counts.items() if count > 1]


def upsert_records(
    engine: Engine,
    table: str,
    key_columns: Sequence[str],
    records: Sequence[dict[str, Any]],
    batch_id: uuid.UUID,
    source_release: str | None = None,
) -> LoadResult:
    """Load `records` into `table` idempotently.

    Each record must contain every key column, `payload` (any JSON-serialisable
    value) and `_source_url`. All rows are written in ONE transaction: if
    anything fails, nothing is written.
    """
    validate_identifier(table)
    for column in key_columns:
        validate_identifier(column)
    if not records:
        return LoadResult(received=0, inserted=0, updated=0)

    duplicates = find_duplicate_keys(records, key_columns)
    if duplicates:
        raise DuplicateKeyError(
            f"{len(duplicates)} duplicate key(s) in batch for {table}, e.g. {duplicates[:3]}"
        )

    rows = [
        {
            **{column: record[column] for column in key_columns},
            "payload": json.dumps(record["payload"], ensure_ascii=False),
            "_record_hash": record_hash(record["payload"]),
            "_source_url": record["_source_url"],
            "_source_release": record.get("_source_release", source_release),
            "_batch_id": batch_id,
        }
        for record in records
    ]

    columns = [*key_columns, *METADATA_COLUMNS]
    column_list = ", ".join(columns)
    placeholders = ", ".join(
        "CAST(:payload AS jsonb)" if column == "payload" else f":{column}" for column in columns
    )
    key_list = ", ".join(key_columns)
    updates = ", ".join(f"{column} = EXCLUDED.{column}" for column in METADATA_COLUMNS)

    with engine.begin() as conn:
        # 1. Bulk-insert the batch into a temporary table that disappears at commit.
        conn.execute(
            text(f"CREATE TEMP TABLE _load_batch (LIKE {table} INCLUDING DEFAULTS) ON COMMIT DROP")
        )
        conn.execute(text(f"INSERT INTO _load_batch ({column_list}) VALUES ({placeholders})"), rows)
        # 2. One set-based upsert. The WHERE clause skips identical payloads, and
        #    xmax = 0 is PostgreSQL's way of telling a fresh insert from an update.
        outcome = (
            conn.execute(
                text(
                    f"""
                INSERT INTO {table} ({column_list})
                SELECT {column_list} FROM _load_batch
                ON CONFLICT ({key_list}) DO UPDATE
                    SET {updates}, _ingested_at = now()
                    WHERE {table}._record_hash IS DISTINCT FROM EXCLUDED._record_hash
                RETURNING (xmax = 0) AS inserted
                """
                )
            )
            .scalars()
            .all()
        )

    result = LoadResult(
        received=len(rows), inserted=sum(outcome), updated=len(outcome) - sum(outcome)
    )
    logger.info(
        "Loaded %s: received=%d inserted=%d updated=%d unchanged=%d",
        table,
        result.received,
        result.inserted,
        result.updated,
        result.unchanged,
    )
    return result
