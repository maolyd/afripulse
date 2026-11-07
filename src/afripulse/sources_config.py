"""Read config/sources.yml and the country reference file."""

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from afripulse.config import PROJECT_ROOT

SOURCES_PATH = PROJECT_ROOT / "config" / "sources.yml"


@lru_cache(maxsize=1)
def load_sources_config(path: Path = SOURCES_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def get_source(source_id: str) -> dict[str, Any]:
    sources = load_sources_config()["sources"]
    if source_id not in sources:
        raise KeyError(f"Unknown source '{source_id}'. Known: {sorted(sources)}")
    return sources[source_id]


def load_country_codes() -> list[str]:
    """ISO3 codes of the countries in scope (ADR 0001), sorted."""
    relative = load_sources_config()["reference"]["countries_file"]
    with (PROJECT_ROOT / relative).open(encoding="utf-8", newline="") as handle:
        return sorted(row["iso3"] for row in csv.DictReader(handle))
