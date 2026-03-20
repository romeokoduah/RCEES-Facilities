# RCEES Facilities Management System

A web application for booking and managing facilities at the **Regional Centre for Energy & Environmental Sustainability (RCEES)**, University of Energy and Natural Resources (UENR), Sunyani, Ghana.

## Features

- **18 facilities** across 8 categories (labs, lecture halls, seminar rooms, auditorium, studio, outdoor spaces, etc.)
- Real-time calendar slot booking with conflict detection
- Tiered pricing (hourly / half-day / full-day) with 1.5x weekend rates
- Guest booking with `RCEES-XXXXX` reference tracking
- Admin approval workflow with email payment links
- Payment gateway support (MoMo / Card / Cash)
- Invoice and receipt generation
- 10 equipment rental add-ons
- 7 discount codes with smart validation
- Maintenance scheduling that blocks bookings
- Admin dashboard with revenue analytics and occupancy metrics
- Reviews and ratings
- 4-tier role system (admin / manager / staff / user)
- Email notifications (SMTP or simulated mode)

## Quick Start

### Prerequisites

- Python 3.8+

### Run

```bash
python run.py
```

The server starts at **http://localhost:8000**. Dependencies are auto-installed from `requirements.txt` if missing, and the SQLite database is initialized with seed data on first run.

Also works from Jupyter:
```python
%run run.py
```

### Default Admin Login

- **Email:** admin@rcees.uenr.edu.gh
- **Password:** rcees2024

## Tech Stack

- **Backend:** FastAPI + SQLite (raw SQL, no ORM)
- **Frontend:** Single-page HTML/CSS/JS served by FastAPI
- **Email:** SMTP (configurable via environment variables)

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `SMTP_HOST` | SMTP server hostname | _(disabled)_ |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USER` | SMTP username | _(disabled)_ |
| `SMTP_PASS` | SMTP password | |
| `SMTP_FROM` | Sender email address | `noreply@rcees.uenr.edu.gh` |
| `SERVER_URL` | Base URL for email links | `http://localhost:8000` |

When `SMTP_HOST` and `SMTP_USER` are not set, emails run in simulation mode (logged to console and database).

## Project Structure

```
├── run.py                  # Entry point
├── requirements.txt        # Python dependencies
├── backend/
│   ├── app.py              # FastAPI application factory
│   ├── config.py           # Configuration and constants
│   ├── database.py         # SQLite schema, seed data, helpers
│   ├── emails.py           # Email notification service
│   └── routes/
│       ├── auth.py          # Login & registration
│       ├── bookings.py      # Bookings, payments, approvals
│       ├── facilities.py    # Facility & category management
│       ├── maintenance.py   # Maintenance scheduling
│       ├── discounts.py     # Discount codes
│       ├── invoices.py      # Invoice generation
│       └── misc.py          # Equipment, users, reviews, analytics
└── frontend/
    └── index.html           # Single-page frontend
```

## License

All rights reserved. RCEES-UENR.
