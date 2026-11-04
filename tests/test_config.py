"""Unit tests for afripulse.config.

These never touch a real database or the real .env file:
`_env_file=None` disables .env loading, and monkeypatch sets fake variables
that are automatically removed after each test.
"""

import pytest
from pydantic import ValidationError

from afripulse.config import Settings

FAKE_PASSWORD = "s3cr3t-value"


@pytest.fixture
def db_env(monkeypatch):
    """Provide a minimal, valid set of database environment variables."""
    monkeypatch.setenv("AFRIPULSE_DB_USER", "test_user")
    monkeypatch.setenv("AFRIPULSE_DB_PASSWORD", FAKE_PASSWORD)
    monkeypatch.setenv("AFRIPULSE_DB_NAME", "test_db")


def test_settings_load_from_environment(db_env):
    settings = Settings(_env_file=None)

    assert settings.db_user == "test_user"
    assert settings.db_name == "test_db"
    assert settings.db_host == "localhost"  # default
    assert settings.db_port == 5432  # default


def test_password_is_masked_when_printed(db_env):
    settings = Settings(_env_file=None)

    assert FAKE_PASSWORD not in repr(settings)
    assert FAKE_PASSWORD not in str(settings)
    assert settings.db_password.get_secret_value() == FAKE_PASSWORD


def test_sqlalchemy_url_is_built_and_hides_password(db_env):
    url = Settings(_env_file=None).sqlalchemy_url

    assert url.drivername == "postgresql+psycopg"
    assert url.username == "test_user"
    assert url.database == "test_db"
    assert FAKE_PASSWORD not in str(url)


def test_missing_credentials_fail_fast(monkeypatch):
    monkeypatch.delenv("AFRIPULSE_DB_USER", raising=False)
    monkeypatch.delenv("AFRIPULSE_DB_PASSWORD", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_invalid_port_is_rejected(db_env, monkeypatch):
    monkeypatch.setenv("AFRIPULSE_DB_PORT", "99999")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
