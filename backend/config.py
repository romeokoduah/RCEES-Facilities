"""RCEES Facilities - Configuration"""
from pathlib import Path
import os

try:
    BASE_DIR = Path(__file__).resolve().parent.parent
except NameError:
    BASE_DIR = Path.cwd()

DB_PATH = BASE_DIR / "rcees_facilities.db"
UPLOAD_DIR = BASE_DIR / "uploads"
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = BASE_DIR / "static"
INVOICE_DIR = BASE_DIR / "invoices"

for d in [UPLOAD_DIR, UPLOAD_DIR/"facilities", STATIC_DIR, INVOICE_DIR]:
    d.mkdir(exist_ok=True)

ADMIN_EMAIL = "admin@rcees.uenr.edu.gh"
ADMIN_PASSWORD = "rcees2024"

SLOT_START_HOUR = 7
SLOT_END_HOUR = 21
CURRENCY = "GH₵"
DEFAULT_PORT = 8000

# Email (set these to enable real emails, otherwise runs in simulation mode)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@rcees.uenr.edu.gh")
SMTP_ENABLED = bool(SMTP_HOST and SMTP_USER)

# Server URL for email links
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:8000")

# Organization info for invoices
ORG_NAME = "Regional Centre for Energy & Environmental Sustainability"
ORG_SHORT = "RCEES-UENR"
ORG_ADDRESS = "University of Energy and Natural Resources, Sunyani, Bono Region, Ghana"
ORG_PHONE = "+233 XX XXX XXXX"
ORG_WEBSITE = "https://rcees.uenr.edu.gh"
TAX_ID = "GHA-XXXXXXXX"
TAX_RATE = 0.0  # 0% — set to 0.125 for 12.5% VAT if needed
