# City Library Management

A beginner-friendly library system built with **Python, FastAPI and SQLite**. It includes a web dashboard, REST API, sample data, SQL reports and tests. SQLite needs no separate database server.

## Run the project

Open PowerShell in the project folder:

```powershell
.\venv\Scripts\Activate.ps1
python -m database.seed
uvicorn app.main:app --reload
```

If the `venv` folder does not exist, create it and install packages first:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Open the dashboard at <http://127.0.0.1:8000> or interactive API docs at <http://127.0.0.1:8000/docs>. Stop the server with `Ctrl+C`.

## Main features

- Books can have multiple authors and physical copies across three branches.
- Librarians can add books, issue copies and record returns.
- Members can hold up to 3 active loans. Loans last 14 days; late returns cost ₹10 per day.
- Members can view their own loans and fines. Fine payment is a demo that records paid status; it does not charge money.
- Librarians can view overdue loans, most-borrowed books, members and fines.
- Partner catalogue access uses an API key and secret.

When adding a book, enter 0–50 copies for each branch, with at least one copy overall.

## Demo video

[Watch the project demo](https://drive.google.com/file/d/1qR3gaKrIb6I3D1jhxOHfcOBDzBHmFLDQ/view?usp=drive_link)

## Demo logins

- Librarian: `admin@library.com` / `admin12345`
- Member: `aisha@example.com` / `member12345`
- Second member: `rahul@example.com` / `member12345`

These passwords and partner credentials are for local practice only.

## Partner catalogue

Set `PARTNER_API_KEY` and `PARTNER_API_SECRET` in `.env`, then restart the server. For local practice, use the matching demo values in `.env.example` and the Postman collection.

The API request must include both headers:

```text
X-API-Key: <your key>
X-API-Secret: <your secret>
```

## API routes

| Method | Route | Access |
|---|---|---|
| GET | `/api/books`, `/api/branches` | Public |
| GET | `/api/books/{book_id}/copies` | Public |
| GET | `/api/partner/books` | Partner key + secret |
| POST | `/api/books` | Librarian |
| POST | `/api/members` | Public registration |
| POST | `/api/members/login` | Public login |
| POST | `/api/members/logout` | Member token |
| GET | `/api/members`, `/api/loans`, `/api/fines` | Librarian |
| POST | `/api/librarians/login` | Public login |
| POST | `/api/librarians/logout` | Librarian session |
| POST | `/api/loans` | Librarian checkout |
| POST | `/api/loans/{loan_id}/return` | Librarian return |
| GET | `/api/me/loans`, `/api/me/fines` | Member token |
| POST | `/api/fines/{fine_id}/pay` | Member token; own fine only |
| GET | `/api/reports/overdue`, `/api/reports/most-borrowed` | Librarian |

API errors use `{ "error": { "code": "...", "message": "..." } }`. Member requests use `Authorization: Bearer <token>`; librarian requests use a session cookie.

## Project files

- `app/main.py` — API routes, validation and library rules
- `app/db.py` — SQLite connection, queries and transactions
- `database/schema.sql` — tables, relationships, constraints and indexes
- `database/seed.py` — repeatable sample-data setup
- `database/reports.sql` — plain SQL reports
- `static/` — web dashboard
- `postman/library_api.json` — Postman collection
- `scripts/test_api.ps1` — Windows curl checks
- `tests/test_api.py` — automated tests

## Tests

```powershell
python -m unittest discover -s tests -v
.\scripts\test_api.ps1
```

Import `postman/library_api.json` into Postman to try the API requests. The schema and reports use SQLite SQL.
