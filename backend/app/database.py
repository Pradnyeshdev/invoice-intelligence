import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DATABASE_PATH = Path(__file__).resolve().parents[1] / "invoice_intelligence.sqlite3"


class DatabaseError(Exception):
    """Safe, user-independent database failure."""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection: sqlite3.Connection | None = None
    try:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(DATABASE_PATH)
        connection.row_factory = sqlite3.Row
        yield connection
        connection.commit()
    except (sqlite3.Error, OSError):
        if connection is not None:
            connection.rollback()
        raise DatabaseError("The local database operation failed.") from None
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if connection is not None:
            connection.close()


def initialize_database() -> None:
    """Create the local SQLite tables if they do not already exist."""
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_files (
                upload_id TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id TEXT NOT NULL UNIQUE,
                original_filename TEXT NOT NULL,
                invoice_number TEXT,
                invoice_date TEXT,
                vendor_name TEXT,
                subtotal TEXT,
                tax TEXT,
                total TEXT,
                currency TEXT,
                is_valid INTEGER NOT NULL CHECK (is_valid IN (0, 1)),
                errors_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                checks_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
