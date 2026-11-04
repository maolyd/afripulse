"""Smoke tests: confirm the development environment is correctly set up.

A 'smoke test' is a quick, basic check that the system starts at all,
before testing detailed behaviour. If these fail, nothing else will work.
"""

import importlib
import sys

import pytest

import afripulse

# Every runtime library the pipeline depends on.
# Note: some packages install under a different import name (PyYAML -> yaml).
REQUIRED_MODULES = [
    "requests",
    "tenacity",
    "pandas",
    "openpyxl",
    "sqlalchemy",
    "psycopg",
    "dotenv",
    "pydantic",
    "pydantic_settings",
    "yaml",
]


def test_python_version_is_3_12():
    """The project is pinned to Python 3.12 for dbt/Airflow compatibility."""
    assert sys.version_info[:2] == (3, 12)


def test_package_is_importable_and_versioned():
    """The afripulse package is installed and exposes a version string."""
    assert afripulse.__version__ == "0.1.0"


@pytest.mark.parametrize("module_name", REQUIRED_MODULES)
def test_required_module_is_importable(module_name):
    """Each runtime dependency can be imported."""
    importlib.import_module(module_name)
