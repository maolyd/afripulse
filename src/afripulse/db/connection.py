"""Create and verify PostgreSQL connections for AfriPulse.

Run directly to check connectivity:
    python -m afripulse.db.connection
"""

from sqlalchemy import Engine, create_engine, text

from afripulse.config import Settings, get_settings


def get_engine(settings: Settings | None = None) -> Engine:
    """Create a SQLAlchemy engine (connection pool) from settings.

    Args:
        settings: Optional settings override (useful in tests).
                  Defaults to the cached application settings.
    """
    settings = settings or get_settings()
    return create_engine(
        settings.sqlalchemy_url,
        pool_pre_ping=True,  # test a pooled connection before using it
    )


def check_connection(engine: Engine) -> dict[str, str]:
    """Run a lightweight query proving the connection works.

    Returns:
        The connected user, database and server version.
    """
    query = text("SELECT current_user, current_database(), current_setting('server_version')")
    with engine.connect() as conn:
        user, database, version = conn.execute(query).one()
    return {"user": user, "database": database, "server_version": version}


if __name__ == "__main__":
    engine = get_engine()
    try:
        print(f"Connected OK -> {check_connection(engine)}")
    finally:
        engine.dispose()  # always close connections, even after an error
