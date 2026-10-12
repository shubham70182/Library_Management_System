import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.db import get_database_path, normalize_sql, password_hash, verify_password
from app.main import (
    BookInput,
    MemberInput,
    add_book,
    app,
    error_response,
    require_librarian,
    require_member,
    require_partner,
)
from database.seed import seed_database


class PasswordTests(unittest.TestCase):
    def test_password_hash_matches_original_password(self):
        saved_hash = password_hash("safe-sample-password")

        self.assertTrue(verify_password("safe-sample-password", saved_hash))
        self.assertFalse(verify_password("wrong-password", saved_hash))


class DatabaseConfigTests(unittest.TestCase):
    def test_connection_uses_configured_sqlite_path(self):
        with patch.dict(
            os.environ,
            {"DB_PATH": "database/test-library.sqlite3"},
            clear=True,
        ):
            path = get_database_path()

        self.assertTrue(
            str(path).endswith("database\\test-library.sqlite3")
        )

    def test_parameterized_query_is_adapted_for_sqlite(self):
        sql = normalize_sql("SELECT member_id FROM members WHERE member_id = %s FOR UPDATE")

        self.assertEqual(sql, "SELECT member_id FROM members WHERE member_id = ?")

    def test_schema_and_sample_data_load_into_sqlite(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "library.sqlite3"
            with patch.dict(os.environ, {"DB_PATH": str(database_path)}, clear=True):
                seed_database()
                seed_database()

            connection = sqlite3.connect(database_path)
            try:
                counts = {
                    table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ("branches", "books", "members", "loans", "fines")
                }
                foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
            finally:
                connection.close()

        self.assertEqual(counts, {
            "branches": 3,
            "books": 3,
            "members": 2,
            "loans": 3,
            "fines": 2,
        })
        self.assertEqual(foreign_key_errors, [])


class ApiTests(unittest.TestCase):
    def test_book_copies_can_be_added_to_multiple_branches(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "library.sqlite3"
            with patch.dict(os.environ, {"DB_PATH": str(database_path)}, clear=True):
                seed_database()
                book = BookInput(
                    title="Branch Test Book",
                    branch_copies={1: 4, 2: 3, 3: 5},
                )
                with patch("app.main.require_librarian", return_value=1):
                    result = add_book(book, "test-session")

                connection = sqlite3.connect(database_path)
                try:
                    copies = connection.execute(
                        """
                        SELECT branch_id, COUNT(*)
                        FROM book_copies
                        WHERE book_id = ?
                        GROUP BY branch_id
                        ORDER BY branch_id
                        """,
                        (result["book_id"],),
                    ).fetchall()
                finally:
                    connection.close()

        self.assertEqual(copies, [(1, 4), (2, 3), (3, 5)])

    def test_member_access_requires_login(self):
        with self.assertRaises(HTTPException) as raised:
            require_member(None)

        self.assertEqual(raised.exception.status_code, 401)

    def test_librarian_access_requires_session(self):
        with self.assertRaises(HTTPException) as raised:
            require_librarian(None)

        self.assertEqual(raised.exception.status_code, 401)

    def test_partner_access_requires_both_credentials(self):
        with patch.dict(
            os.environ,
            {"PARTNER_API_KEY": "sample-key", "PARTNER_API_SECRET": "sample-secret"},
        ):
            with self.assertRaises(HTTPException) as raised:
                require_partner(None, None)

        self.assertEqual(raised.exception.status_code, 401)

    def test_error_response_uses_one_json_shape(self):
        response = error_response(401, "LOGIN_REQUIRED", "Member login required")

        self.assertEqual(
            json.loads(response.body),
            {
                "error": {
                    "code": "LOGIN_REQUIRED",
                    "message": "Member login required",
                }
            },
        )

    def test_invalid_member_input_is_rejected(self):
        with self.assertRaises(ValidationError):
            MemberInput.model_validate(
                {
                    "member_name": "",
                    "email": "not-an-email",
                    "password": "short",
                }
            )

    def test_required_api_routes_are_registered(self):
        paths = {route.path for route in app.routes}

        self.assertIn("/api/books", paths)
        self.assertIn("/api/loans/{loan_id}/return", paths)
        self.assertIn("/api/reports/most-borrowed", paths)


if __name__ == "__main__":
    unittest.main()
