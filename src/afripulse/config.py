"""Centralised, typed configuration for AfriPulse.

Settings are read from environment variables (prefixed AFRIPULSE_), which are
loaded from the project's .env file if present. Real environment variables
always take priority over .env values, which is how production systems inject
secrets without files.

Usage:
    from afripulse.config import get_settings
    settings = get_settings()
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# src/afripulse/config.py -> parents[0]=afripulse, [1]=src, [2]=project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings, validated on creation."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="AFRIPULSE_",
        extra="ignore",
    )

    env: str = "dev"

    db_host: str = "localhost"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "afripulse"
    db_user: str  # required: no default, so a missing value fails fast
    db_password: SecretStr  # required, and masked when printed or logged

    @property
    def sqlalchemy_url(self) -> URL:
        """Build the database URL safely (special characters are escaped)."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the settings, loaded once and reused (cached)."""
    return Settings()
