PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS branches (
    branch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_name TEXT NOT NULL UNIQUE,
    address TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS books (
    book_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    isbn TEXT UNIQUE,
    published_year INTEGER
        CHECK (published_year IS NULL OR published_year BETWEEN 1000 AND 2100)
);

CREATE TABLE IF NOT EXISTS authors (
    author_id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS book_authors (
    book_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    PRIMARY KEY (book_id, author_id),
    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES authors(author_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS book_copies (
    copy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    branch_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'loaned')),
    FOREIGN KEY (book_id) REFERENCES books(book_id),
    FOREIGN KEY (branch_id) REFERENCES branches(branch_id)
);

CREATE TABLE IF NOT EXISTS members (
    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    joined_date TEXT NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS loans (
    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    copy_id INTEGER NOT NULL,
    issued_by INTEGER NOT NULL,
    issued_at TEXT NOT NULL,
    due_date TEXT NOT NULL,
    returned_at TEXT,
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (copy_id) REFERENCES book_copies(copy_id),
    FOREIGN KEY (issued_by) REFERENCES staff(staff_id)
);

CREATE TABLE IF NOT EXISTS fines (
    fine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id INTEGER NOT NULL UNIQUE,
    fine_amount REAL NOT NULL CHECK (fine_amount > 0),
    is_paid INTEGER NOT NULL DEFAULT 0 CHECK (is_paid IN (0, 1)),
    paid_at TEXT,
    FOREIGN KEY (loan_id) REFERENCES loans(loan_id)
);

CREATE TABLE IF NOT EXISTS member_tokens (
    token_hash TEXT PRIMARY KEY,
    member_id INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES members(member_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS librarian_sessions (
    session_hash TEXT PRIMARY KEY,
    staff_id INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_copies_book_branch
    ON book_copies(book_id, branch_id);
CREATE INDEX IF NOT EXISTS idx_copies_status
    ON book_copies(status);
CREATE INDEX IF NOT EXISTS idx_loans_member_active
    ON loans(member_id, returned_at);
CREATE INDEX IF NOT EXISTS idx_loans_overdue
    ON loans(returned_at, due_date);
CREATE INDEX IF NOT EXISTS idx_loans_copy
    ON loans(copy_id);
CREATE INDEX IF NOT EXISTS idx_member_tokens_expiry
    ON member_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_librarian_sessions_expiry
    ON librarian_sessions(expires_at);
