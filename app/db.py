import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import NoReturn

from dotenv import load_dotenv
from fastapi import HTTPException

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")


class DatabaseConfigurationError(Exception):
    pass


def get_database_path() -> Path:
    configured_path = os.getenv("DB_PATH")
    if configured_path:
        path = Path(configured_path)
        if not path.is_absolute():
            path = PROJECT_DIR / path
    else:
        path = PROJECT_DIR / "database" / "library.sqlite3"

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(get_database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    schema_path = PROJECT_DIR / "database" / "schema.sql"
    connection = get_connection()
    try:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
    finally:
        connection.close()


def normalize_sql(sql: str) -> str:
    return sql.replace("%s", "?").replace("FOR UPDATE", "").strip()


def normalize_values(values: tuple) -> tuple:
    return tuple(
        value.isoformat() if isinstance(value, (date, datetime)) else value
        for value in values
    )


class SQLiteCursor:
    def __init__(self, connection: sqlite3.Connection):
        self._cursor = connection.cursor()

    def execute(self, sql: str, values: tuple = ()):
        self._cursor.execute(normalize_sql(sql), normalize_values(values))
        return self

    def executemany(self, sql: str, values):
        rows = (normalize_values(row) for row in values)
        self._cursor.executemany(normalize_sql(sql), rows)
        return self

    def __getattr__(self, name):
        return getattr(self._cursor, name)


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 200_000
    ).hex()
    return f"{salt}${hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, old_hash = stored_hash.split("$")
        new_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 200_000
        ).hex()
        return secrets.compare_digest(new_hash, old_hash)
    except (ValueError, AttributeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def fetch_all(sql: str, values: tuple = ()) -> list[dict]:
    connection = get_connection()
    try:
        cursor = connection.execute(normalize_sql(sql), normalize_values(values))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


@contextmanager
def transaction():
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield SQLiteCursor(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def api_error(status_code: int, code: str, message: str) -> NoReturn:
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )
