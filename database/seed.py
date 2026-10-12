from datetime import date, timedelta

from app.db import get_connection, initialize_database, password_hash


def seed_database() -> None:
    initialize_database()
    today = date.today()
    connection = get_connection()

    try:
        connection.executemany(
            """
            INSERT OR IGNORE INTO branches (branch_id, branch_name, address)
            VALUES (?, ?, ?)
            """,
            [
                (1, "Central Library", "10 Main Street"),
                (2, "North Branch", "25 North Road"),
                (3, "South Branch", "8 Garden Avenue"),
            ],
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO books (book_id, title, isbn, published_year)
            VALUES (?, ?, ?, ?)
            """,
            [
                (1, "Python Basics", "9780000000001", 2024),
                (2, "The Secret Garden", "9780000000002", 2020),
                (3, "A Short History of Time", "9780000000003", 2019),
            ],
        )

        authors = [
            (1, "Ravi Kumar"),
            (2, "Frances Hodgson Burnett"),
            (3, "Stephen Hawking"),
        ]
        for book_id, author_name in authors:
            connection.execute(
                "INSERT OR IGNORE INTO authors (author_id, author_name) VALUES (?, ?)",
                (book_id, author_name),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO book_authors (book_id, author_id)
                VALUES (?, ?)
                """,
                (book_id, book_id),
            )

        connection.executemany(
            """
            INSERT OR IGNORE INTO book_copies (copy_id, book_id, branch_id, status)
            VALUES (?, ?, ?, ?)
            """,
            [
                (1, 1, 1, "available"),
                (2, 2, 2, "loaned"),
                (3, 1, 2, "available"),
                (4, 3, 3, "available"),
                (5, 3, 3, "available"),
                (6, 3, 3, "available"),
            ],
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO members
                (member_id, member_name, email, password_hash, joined_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                1,
                "Aisha Khan",
                "aisha@example.com",
                password_hash("member12345"),
                (today - timedelta(days=90)).isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO members
                (member_id, member_name, email, password_hash, joined_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                2,
                "Rahul Sharma",
                "rahul@example.com",
                password_hash("member12345"),
                (today - timedelta(days=60)).isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO staff (staff_id, staff_name, email, password_hash)
            VALUES (?, ?, ?, ?)
            """,
            (1, "Library Desk", "admin@library.com", password_hash("admin12345")),
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO loans
                (loan_id, member_id, copy_id, issued_by, issued_at, due_date, returned_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    2,
                    1,
                    1,
                    (today - timedelta(days=18)).isoformat(),
                    (today - timedelta(days=4)).isoformat(),
                    (today - timedelta(days=2)).isoformat(),
                ),
                (
                    2,
                    1,
                    2,
                    1,
                    (today - timedelta(days=20)).isoformat(),
                    (today - timedelta(days=6)).isoformat(),
                    None,
                ),
                (
                    3,
                    1,
                    3,
                    1,
                    (today - timedelta(days=10)).isoformat(),
                    (today - timedelta(days=3)).isoformat(),
                    (today - timedelta(days=1)).isoformat(),
                ),
            ],
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO fines (fine_id, loan_id, fine_amount, is_paid)
            VALUES (?, ?, ?, ?)
            """,
            [(1, 1, 20.00, 0), (2, 3, 20.00, 0)],
        )
        connection.commit()
        print("Sample library data is ready.")
        print("Librarian login: admin@library.com / admin12345")
        print("Member login: aisha@example.com / member12345")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    seed_database()
