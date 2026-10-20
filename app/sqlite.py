"""SQLite connection tweaks. Imported once for its side effect (event listener)."""
import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine


def _unicode_lower(value):
    return value.lower() if isinstance(value, str) else value


@event.listens_for(Engine, "connect")
def configure_sqlite(dbapi_connection, _connection_record):
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return  # other databases (PostgreSQL, ...) need none of this

    # SQLite's built-in lower() only understands ASCII, so ILIKE searches would never match
    # Cyrillic case-insensitively ("өвөр" vs "Өвөрхангай"). Replace it with Python's Unicode-aware
    # version; SQLAlchemy's ilike() compiles to lower(col) LIKE lower(:term).
    dbapi_connection.create_function("lower", 1, _unicode_lower, deterministic=True)

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")  # readers don't block the writer (several gunicorn workers)
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
