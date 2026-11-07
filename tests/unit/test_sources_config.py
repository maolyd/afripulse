"""Validate the structure of config/sources.yml (no network access)."""

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.yml"

REQUIRED_KEYS = {
    "enabled",
    "connector",
    "description",
    "licence",
    "raw_table",
    "natural_key",
    "incremental",
}
KNOWN_CONNECTORS = {"worldbank_api", "imf_datamapper_api", "csv_file", "excel_file"}
RAW_SCHEMAS = {"raw", "raw_synthetic"}


@pytest.fixture(scope="module")
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sources(config) -> dict:
    return config["sources"]


def test_config_defines_sources(sources):
    assert sources, "no sources configured"


def test_every_source_has_required_keys(sources):
    for name, source in sources.items():
        missing = REQUIRED_KEYS - source.keys()
        assert not missing, f"{name} is missing {sorted(missing)}"


def test_connectors_are_known(sources):
    for name, source in sources.items():
        assert source["connector"] in KNOWN_CONNECTORS, f"{name}: unknown connector"


def test_raw_tables_are_in_raw_schemas_and_unique(sources):
    tables = [source["raw_table"] for source in sources.values()]
    assert len(set(tables)) == len(tables), "two sources share a raw table"
    for table in tables:
        assert table.split(".")[0] in RAW_SCHEMAS, f"{table} is not in a raw schema"


def test_natural_keys_are_non_empty_lists(sources):
    for name, source in sources.items():
        key = source["natural_key"]
        assert isinstance(key, list) and key, f"{name}: natural_key must be a non-empty list"


def test_file_sources_declare_landing_path(sources):
    for name, source in sources.items():
        if source["connector"] in {"csv_file", "excel_file"}:
            assert source.get("landing_path"), f"{name}: missing landing_path"


def test_reference_file_exists(config):
    assert (PROJECT_ROOT / config["reference"]["countries_file"]).is_file()
