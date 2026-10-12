from __future__ import annotations

import hmac
import logging
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import Cookie, FastAPI, Header, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from starlette.requests import Request

from app.db import (
    DatabaseConfigurationError,
    api_error,
    fetch_all,
    initialize_database,
    password_hash,
    token_hash,
    transaction,
    verify_password,
)

BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="City Library API", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


class BookInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    isbn: str | None = Field(default=None, max_length=20)
    published_year: int | None = Field(default=None, ge=1000, le=2100)
    author_names: list[str] = Field(default_factory=list, max_length=10)
    branch_id: int | None = Field(default=None, gt=0)
    copies: int = Field(default=1, ge=1, le=50)
    branch_copies: dict[int, int] | None = None


class MemberInput(BaseModel):
    member_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class LoanInput(BaseModel):
    member_id: int = Field(gt=0)
    copy_id: int = Field(gt=0)


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return error_response(
            exc.status_code,
            exc.detail.get("code", "REQUEST_ERROR"),
            exc.detail.get("message", "Request failed"),
        )
    return error_response(exc.status_code, "REQUEST_ERROR", str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, _exc: RequestValidationError):
    return error_response(422, "VALIDATION_ERROR", "Invalid request data")


@app.exception_handler(sqlite3.Error)
async def database_error_handler(_request: Request, _exc: sqlite3.Error):
    logging.exception("Database request failed")
    return error_response(503, "DATABASE_ERROR", "Database request failed")


@app.exception_handler(DatabaseConfigurationError)
async def database_config_error_handler(
    _request: Request, exc: DatabaseConfigurationError
):
    return error_response(503, "DATABASE_CONFIG_ERROR", str(exc))


@app.exception_handler(Exception)
async def unexpected_error_handler(_request: Request, _exc: Exception):
    logging.exception("Unexpected API error")
    return error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


def require_member(authorization: str | None) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        api_error(401, "LOGIN_REQUIRED", "Member login required")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        api_error(401, "LOGIN_REQUIRED", "Member login required")

    rows = fetch_all(
        """
        SELECT member_id
        FROM member_tokens
        WHERE token_hash = %s AND datetime(expires_at) > datetime('now')
        """,
        (token_hash(token),),
    )
    if not rows:
        api_error(401, "INVALID_TOKEN", "Member token is invalid or expired")
    return rows[0]["member_id"]


def require_librarian(session: str | None) -> int:
    if not session:
        api_error(401, "LOGIN_REQUIRED", "Librarian login required")

    rows = fetch_all(
        """
        SELECT staff_id
        FROM librarian_sessions
        WHERE session_hash = %s AND datetime(expires_at) > datetime('now')
        """,
        (token_hash(session),),
    )
    if not rows:
        api_error(401, "INVALID_SESSION", "Librarian session is invalid or expired")
    return rows[0]["staff_id"]


def require_partner(api_key: str | None, api_secret: str | None) -> None:
    expected_key = os.getenv("PARTNER_API_KEY", "")
    expected_secret = os.getenv("PARTNER_API_SECRET", "")
    if not expected_key or not expected_secret:
        api_error(503, "PARTNER_NOT_CONFIGURED", "Partner access is not configured")
    if not (
        hmac.compare_digest(api_key or "", expected_key)
        and hmac.compare_digest(api_secret or "", expected_secret)
    ):
        api_error(401, "INVALID_PARTNER_CREDENTIALS", "Partner credentials are invalid")


def get_books() -> list[dict]:
    return fetch_all(
        """
        SELECT b.book_id, b.title, b.isbn, b.published_year,
               GROUP_CONCAT(DISTINCT a.author_name) AS authors,
               COUNT(DISTINCT CASE WHEN c.status = 'available' THEN c.copy_id END)
                   AS available_copies
        FROM books b
        LEFT JOIN book_authors ba ON ba.book_id = b.book_id
        LEFT JOIN authors a ON a.author_id = ba.author_id
        LEFT JOIN book_copies c ON c.book_id = b.book_id
        GROUP BY b.book_id, b.title, b.isbn, b.published_year
        ORDER BY b.title
        """
    )


@app.get("/api/books")
def list_books():
    return get_books()


@app.get("/api/branches")
def list_branches():
    return fetch_all(
        """
        SELECT branch_id, branch_name, address
        FROM branches
        ORDER BY branch_name
        """
    )


@app.get("/api/books/{book_id}/copies")
def list_book_copies(book_id: int, branch_id: int | None = None):
    book_rows = fetch_all(
        "SELECT book_id FROM books WHERE book_id = %s",
        (book_id,),
    )
    if not book_rows:
        api_error(404, "BOOK_NOT_FOUND", "Book not found")

    return fetch_all(
        """
        SELECT c.copy_id, c.branch_id, br.branch_name, c.status
        FROM book_copies c
        JOIN branches br ON br.branch_id = c.branch_id
        WHERE c.book_id = %s AND (%s IS NULL OR c.branch_id = %s)
        ORDER BY br.branch_name, c.copy_id
        """,
        (book_id, branch_id, branch_id),
    )


@app.get("/api/partner/books")
def partner_books(
    api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_secret: str | None = Header(default=None, alias="X-API-Secret"),
):
    require_partner(api_key, api_secret)
    return get_books()


@app.post("/api/books", status_code=201)
def add_book(
    book: BookInput,
    librarian_session: str | None = Cookie(default=None),
):
    require_librarian(librarian_session)
    if not book.title.strip():
        api_error(422, "INVALID_BOOK_TITLE", "Book title cannot be empty")
    copies_by_branch = book.branch_copies
    if copies_by_branch is not None and (
        not any(copies_by_branch.values())
        or any(copies < 0 or copies > 50 for copies in copies_by_branch.values())
    ):
        api_error(422, "INVALID_COPIES", "Add 1 to 50 copies per branch")
    if copies_by_branch is None:
        copies_by_branch = {book.branch_id: book.copies} if book.branch_id else {}

    try:
        with transaction() as cursor:
            for branch_id in copies_by_branch:
                cursor.execute(
                    "SELECT branch_id FROM branches WHERE branch_id = %s",
                    (branch_id,),
                )
                if cursor.fetchone() is None:
                    api_error(404, "BRANCH_NOT_FOUND", "Branch not found")

            cursor.execute(
                """
                INSERT INTO books (title, isbn, published_year)
                VALUES (%s, %s, %s)
                RETURNING book_id
                """,
                (book.title.strip(), book.isbn, book.published_year),
            )
            book_id = cursor.fetchone()["book_id"]

            author_names = {
                name.strip().casefold(): name.strip()
                for name in book.author_names
                if name.strip()
            }
            for author_name in author_names.values():
                cursor.execute(
                    """
                    INSERT INTO authors (author_name)
                    VALUES (%s)
                    ON CONFLICT (author_name) DO UPDATE
                    SET author_name = EXCLUDED.author_name
                    RETURNING author_id
                    """,
                    (author_name,),
                )
                author_id = cursor.fetchone()["author_id"]
                cursor.execute(
                    """
                    INSERT INTO book_authors (book_id, author_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (book_id, author_id),
                )

            for branch_id, copies in copies_by_branch.items():
                if copies:
                    cursor.executemany(
                        """
                        INSERT INTO book_copies (book_id, branch_id, status)
                        VALUES (%s, %s, 'available')
                        """,
                        [(book_id, branch_id)] * copies,
                    )
    except sqlite3.IntegrityError:
        api_error(409, "BOOK_CONFLICT", "ISBN already exists")

    return {"book_id": book_id, "message": "Book added"}


@app.post("/api/members", status_code=201)
def register_member(member: MemberInput):
    if not member.member_name.strip():
        api_error(422, "INVALID_MEMBER_NAME", "Member name cannot be empty")

    try:
        with transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO members (member_name, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING member_id
                """,
                (
                    member.member_name.strip(),
                    member.email,
                    password_hash(member.password),
                ),
            )
            member_id = cursor.fetchone()["member_id"]
    except sqlite3.IntegrityError:
        api_error(409, "EMAIL_EXISTS", "This email is already registered")

    return {"member_id": member_id, "message": "Member registered"}


@app.post("/api/members/login")
def member_login(data: LoginInput):
    rows = fetch_all(
        "SELECT member_id, password_hash FROM members WHERE email = %s",
        (data.email,),
    )
    if not rows or not verify_password(data.password, rows[0]["password_hash"]):
        api_error(401, "INVALID_LOGIN", "Email or password is incorrect")

    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    with transaction() as cursor:
        cursor.execute(
            """
            INSERT INTO member_tokens (token_hash, member_id, expires_at)
            VALUES (%s, %s, %s)
            """,
            (token_hash(token), rows[0]["member_id"], expires_at),
        )
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/members/logout", status_code=204)
def member_logout(authorization: str | None = Header(default=None)):
    member_id = require_member(authorization)
    token = authorization.removeprefix("Bearer ").strip()
    with transaction() as cursor:
        cursor.execute(
            "DELETE FROM member_tokens WHERE token_hash = %s AND member_id = %s",
            (token_hash(token), member_id),
        )
    return Response(status_code=204)


@app.post("/api/librarians/login")
def librarian_login(data: LoginInput, response: Response):
    rows = fetch_all(
        "SELECT staff_id, password_hash FROM staff WHERE email = %s",
        (data.email,),
    )
    if not rows or not verify_password(data.password, rows[0]["password_hash"]):
        api_error(401, "INVALID_LOGIN", "Email or password is incorrect")

    session = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with transaction() as cursor:
        cursor.execute(
            """
            INSERT INTO librarian_sessions (session_hash, staff_id, expires_at)
            VALUES (%s, %s, %s)
            """,
            (token_hash(session), rows[0]["staff_id"], expires_at),
        )

    response.set_cookie(
        key="librarian_session",
        value=session,
        httponly=True,
        samesite="strict",
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        max_age=24 * 60 * 60,
        path="/",
    )
    return {"message": "Librarian login successful"}


@app.post("/api/librarians/logout", status_code=204)
def librarian_logout(
    response: Response,
    librarian_session: str | None = Cookie(default=None),
):
    require_librarian(librarian_session)
    with transaction() as cursor:
        cursor.execute(
            "DELETE FROM librarian_sessions WHERE session_hash = %s",
            (token_hash(librarian_session),),
        )
    response.delete_cookie("librarian_session", path="/")
    response.status_code = 204
    return response


@app.get("/api/members")
def list_members(librarian_session: str | None = Cookie(default=None)):
    require_librarian(librarian_session)
    return fetch_all(
        """
        SELECT member_id, member_name, email, joined_date
        FROM members
        ORDER BY member_id
        """
    )


@app.post("/api/loans", status_code=201)
def checkout_book(
    loan: LoanInput,
    librarian_session: str | None = Cookie(default=None),
):
    staff_id = require_librarian(librarian_session)
    issued_date = date.today()
    due_date = issued_date + timedelta(days=14)

    with transaction() as cursor:
        cursor.execute(
            "SELECT member_id FROM members WHERE member_id = %s FOR UPDATE",
            (loan.member_id,),
        )
        if cursor.fetchone() is None:
            api_error(404, "MEMBER_NOT_FOUND", "Member not found")

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM loans
            WHERE member_id = %s AND returned_at IS NULL
            """,
            (loan.member_id,),
        )
        if cursor.fetchone()["total"] >= 3:
            api_error(409, "LOAN_LIMIT_REACHED", "Member already has 3 active loans")

        cursor.execute(
            "SELECT status FROM book_copies WHERE copy_id = %s FOR UPDATE",
            (loan.copy_id,),
        )
        copy = cursor.fetchone()
        if copy is None:
            api_error(404, "COPY_NOT_FOUND", "Book copy not found")
        if copy["status"] != "available":
            api_error(409, "COPY_UNAVAILABLE", "Book copy is not available")

        cursor.execute(
            """
            INSERT INTO loans (member_id, copy_id, issued_by, issued_at, due_date)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING loan_id
            """,
            (loan.member_id, loan.copy_id, staff_id, issued_date, due_date),
        )
        loan_id = cursor.fetchone()["loan_id"]
        cursor.execute(
            "UPDATE book_copies SET status = 'loaned' WHERE copy_id = %s",
            (loan.copy_id,),
        )

    return {
        "loan_id": loan_id,
        "issued_date": issued_date,
        "due_date": due_date,
    }


@app.post("/api/loans/{loan_id}/return")
def return_book(
    loan_id: int,
    librarian_session: str | None = Cookie(default=None),
):
    require_librarian(librarian_session)
    returned_date = date.today()

    with transaction() as cursor:
        cursor.execute(
            "SELECT * FROM loans WHERE loan_id = %s FOR UPDATE",
            (loan_id,),
        )
        loan = cursor.fetchone()
        if loan is None:
            api_error(404, "LOAN_NOT_FOUND", "Loan not found")
        if loan["returned_at"] is not None:
            api_error(409, "ALREADY_RETURNED", "This book has already been returned")

        due_date = loan["due_date"]
        if isinstance(due_date, str):
            due_date = date.fromisoformat(due_date)
        late_days = max(0, (returned_date - due_date).days)
        fine_amount = late_days * 10

        cursor.execute(
            "UPDATE loans SET returned_at = %s WHERE loan_id = %s",
            (returned_date, loan_id),
        )
        cursor.execute(
            "UPDATE book_copies SET status = 'available' WHERE copy_id = %s",
            (loan["copy_id"],),
        )
        if fine_amount:
            cursor.execute(
                """
                INSERT INTO fines (loan_id, fine_amount)
                VALUES (%s, %s)
                """,
                (loan_id, fine_amount),
            )

    return {"late_days": late_days, "fine_amount": fine_amount}


@app.get("/api/loans")
def list_loans(librarian_session: str | None = Cookie(default=None)):
    require_librarian(librarian_session)
    return fetch_all(
        """
        SELECT l.loan_id, l.member_id, m.member_name, l.copy_id,
               b.title, l.issued_at, l.due_date, l.returned_at
        FROM loans l
        JOIN members m ON m.member_id = l.member_id
        JOIN book_copies c ON c.copy_id = l.copy_id
        JOIN books b ON b.book_id = c.book_id
        ORDER BY l.loan_id DESC
        """
    )


@app.get("/api/me/loans")
def my_loans(authorization: str | None = Header(default=None)):
    member_id = require_member(authorization)
    return fetch_all(
        """
        SELECT l.loan_id, b.title, l.issued_at, l.due_date, l.returned_at
        FROM loans l
        JOIN book_copies c ON c.copy_id = l.copy_id
        JOIN books b ON b.book_id = c.book_id
        WHERE l.member_id = %s
        ORDER BY l.loan_id DESC
        """,
        (member_id,),
    )


@app.get("/api/reports/overdue")
def overdue_loans(librarian_session: str | None = Cookie(default=None)):
    require_librarian(librarian_session)
    return fetch_all(
        """
        SELECT l.loan_id, m.member_name, b.title, l.due_date,
               CAST(julianday(CURRENT_DATE) - julianday(l.due_date) AS INTEGER) AS late_days
        FROM loans l
        JOIN members m ON m.member_id = l.member_id
        JOIN book_copies c ON c.copy_id = l.copy_id
        JOIN books b ON b.book_id = c.book_id
        WHERE l.returned_at IS NULL AND l.due_date < CURRENT_DATE
        ORDER BY l.due_date
        """
    )


@app.get("/api/reports/most-borrowed")
def most_borrowed_books(librarian_session: str | None = Cookie(default=None)):
    require_librarian(librarian_session)
    return fetch_all(
        """
        SELECT b.book_id, b.title, COUNT(l.loan_id) AS times_borrowed
        FROM books b
        JOIN book_copies c ON c.book_id = b.book_id
        JOIN loans l ON l.copy_id = c.copy_id
        GROUP BY b.book_id, b.title
        ORDER BY times_borrowed DESC, b.title
        """
    )


@app.get("/api/me/fines")
def my_fines(authorization: str | None = Header(default=None)):
    member_id = require_member(authorization)
    return fetch_all(
        """
        SELECT f.fine_id, f.loan_id, f.fine_amount, f.is_paid, f.paid_at
        FROM fines f
        JOIN loans l ON l.loan_id = f.loan_id
        WHERE l.member_id = %s
        ORDER BY f.fine_id DESC
        """,
        (member_id,),
    )


@app.get("/api/fines")
def list_fines(librarian_session: str | None = Cookie(default=None)):
    require_librarian(librarian_session)
    return fetch_all(
        """
        SELECT f.fine_id, f.loan_id, l.member_id, m.member_name,
               f.fine_amount, f.is_paid, f.paid_at
        FROM fines f
        JOIN loans l ON l.loan_id = f.loan_id
        JOIN members m ON m.member_id = l.member_id
        ORDER BY f.fine_id DESC
        """
    )


@app.post("/api/fines/{fine_id}/pay")
def pay_fine(
    fine_id: int,
    authorization: str | None = Header(default=None),
):
    member_id = require_member(authorization)
    with transaction() as cursor:
        cursor.execute(
            """
            SELECT f.fine_id, f.is_paid, l.member_id
            FROM fines f
            JOIN loans l ON l.loan_id = f.loan_id
            WHERE f.fine_id = %s
            FOR UPDATE
            """,
            (fine_id,),
        )
        fine = cursor.fetchone()
        if fine is None or fine["member_id"] != member_id:
            api_error(404, "FINE_NOT_FOUND", "Fine not found")
        if fine["is_paid"]:
            api_error(409, "FINE_ALREADY_PAID", "Fine has already been paid")

        cursor.execute(
            """
            UPDATE fines
            SET is_paid = 1, paid_at = CURRENT_TIMESTAMP
            WHERE fine_id = %s
            """,
            (fine_id,),
        )

    return {"fine_id": fine_id, "message": "Fine payment recorded"}
