"""Shared types for all extractors.

Every extractor, whatever its source, returns the same thing: an
ExtractResult holding records ready for db.loader.upsert_records.
"""

from dataclasses import dataclass, field
from typing import Any

Record = dict[str, Any]


@dataclass
class ExtractResult:
    records: list[Record] = field(default_factory=list)
    rows_rejected: int = 0
    source_release: str | None = None
