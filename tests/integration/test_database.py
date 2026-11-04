"""Integration tests: verify the real PostgreSQL setup from Phase 1.

Requires Postgres.app running and a valid .env file.
Skip these with:  python -m pytest -m "not integration"
"""

import pytest
from sqlalchemy import text

from afripulse.config import get_settings
from afripulse.db.connection import check_connection, get_engine

pytestmark = pytest.mark.integration  # applies the marker to every test here

LANDING_SCHEMAS = ["raw", "raw_synthetic", "audit"]


@pytest.fixture(scope="module")
def engine():
    """One engine shared by all tests in this file, closed afterwards."""
    eng = get_engine()
    yield eng
    eng.dispose()


def test_connects_as_configured_user_and_database(engine):
    settings = get_settings()
    info = check_connection(engine)

    assert info["user"] == settings.db_user
    assert info["database"] == settings.db_name


@pytest.mark.parametrize("schema", LANDING_SCHEMAS)
def test_landing_schema_exists_and_is_owned_by_app(engine, schema):
    query = text("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = :schema")
    with engine.connect() as conn:
        owner = conn.execute(query, {"schema": schema}).scalar_one_or_none()

    assert owner is not None, f"schema '{schema}' does not exist"
    assert owner == "afripulse_app"


def test_app_user_is_not_a_superuser(engine):
    """Least privilege: the pipeline must never run as a superuser."""
    with engine.connect() as conn:
        is_super = conn.execute(
            text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        ).scalar_one()

    assert is_super is False
