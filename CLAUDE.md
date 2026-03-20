# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RCEES Facilities Management System — a web application for booking and managing facilities at the Regional Centre for Energy & Environmental Sustainability (RCEES), University of Energy and Natural Resources (UENR), Sunyani, Ghana. Currency is GH₵.

## Running the Application

```bash
python run.py
```

Serves at http://localhost:8000. Auto-installs dependencies from `requirements.txt` if missing, kills any existing process on port 8000, and initializes the SQLite database with seed data (18 facilities, 10 equipment items, 7 discount codes). Also works from Jupyter (`%run run.py`) via `nest_asyncio`.

Default admin: `admin@rcees.uenr.edu.gh` / `rcees2024`

## Architecture

**Backend:** FastAPI (Python) with SQLite (WAL mode, foreign keys enabled). No ORM — raw SQL via `sqlite3` with `Row` factory. Database file: `rcees_facilities.db` at project root.

**Frontend:** Single `frontend/index.html` file served by FastAPI at `/`. All frontend code (HTML/CSS/JS) lives in this one file.

**Key backend modules:**
- `backend/config.py` — paths, constants, SMTP config (env vars), org info, pricing defaults
- `backend/database.py` — `get_db()` connection helper, `init_db()` with full schema + seed data, `hash_pw()` (SHA-256)
- `backend/emails.py` — email notifications (SMTP or simulated mode). Set `SMTP_HOST`/`SMTP_USER` env vars to enable real sending
- `backend/app.py` — FastAPI app factory, mounts routers and static files

**API routes** (all under `/api`):
- `routes/auth.py` — `/api/auth/login`, `/api/auth/register`. Auth uses user ID as token (no JWT).
- `routes/bookings.py` — CRUD, guest lookup by email/ref, walk-in bookings, approve/reject workflow, payment processing
- `routes/facilities.py` — CRUD with media upload, availability checking, category management
- `routes/maintenance.py` — scheduling maintenance windows that block bookings
- `routes/discounts.py` — discount code CRUD with validation
- `routes/invoices.py` — invoice/receipt generation linked to bookings
- `routes/misc.py` — equipment, users, reviews, analytics (overview dashboard with trends/occupancy)

## Key Business Logic

- **Pricing:** Tiered (hourly / half-day 4h+ / full-day 8h+) with 1.5x weekend multiplier. Equipment rental adds per-hour cost.
- **Booking flow:** Some facilities require admin approval (`requires_approval` flag). Approved bookings get a payment token emailed to the guest. Conflict detection checks overlapping time slots and maintenance windows.
- **Booking references:** Format `RCEES-XXXXX` (5 alphanumeric chars, no ambiguous characters like 0/O/1/I).
- **Roles:** 4-tier system — admin, manager, staff, user.
- **Uploads:** Facility media stored in `uploads/facilities/`.

## Database

Schema is defined inline in `backend/database.py` (not migration files). `init_db()` uses INSERT-or-ignore pattern for seeding — safe to call repeatedly. Column migrations are handled via `ALTER TABLE ... ADD COLUMN` wrapped in try/except.

Tables: `users`, `categories`, `facilities`, `bookings`, `invoices`, `email_log`, `maintenance`, `discounts`, `equipment`, `reviews`.

## Notes

- No test suite exists.
- No linter/formatter configuration.
