"""RCEES Facilities - Invoice & Receipt Routes"""
import uuid, json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from ..database import get_db
from ..config import ORG_NAME, ORG_SHORT, ORG_ADDRESS, ORG_PHONE, ORG_WEBSITE, TAX_ID, TAX_RATE, CURRENCY

router = APIRouter(prefix="/api/invoices", tags=["invoices"])

def _inv_no():
    """Generate invoice number like INV-2025-00042"""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) as c FROM invoices").fetchone()["c"]
    conn.close()
    year = datetime.now().year
    return f"INV-{year}-{count+1:05d}"

def _receipt_no():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) as c FROM invoices WHERE invoice_type='receipt'").fetchone()["c"]
    conn.close()
    year = datetime.now().year
    return f"RCT-{year}-{count+1:05d}"


def create_invoice_for_booking(booking_id, inv_type="invoice"):
    """Auto-generate invoice/receipt for a booking."""
    conn = get_db()
    b = conn.execute("""SELECT b.*, f.name as fac_name, f.hourly_rate, f.half_day_rate, f.full_day_rate
                        FROM bookings b JOIN facilities f ON b.facility_id=f.id WHERE b.id=?""", (booking_id,)).fetchone()
    if not b:
        conn.close(); return None
    b = dict(b)

    inv_no = _receipt_no() if inv_type == "receipt" else _inv_no()
    iid = str(uuid.uuid4())

    # Build line items
    sh = int(b["start_time"].split(":")[0])
    eh = int(b["end_time"].split(":")[0])
    hrs = eh - sh
    lines = [{"desc": f"{b['fac_name']} — {b['booking_date']} ({b['start_time']}–{b['end_time']}, {hrs}hr{'s' if hrs>1 else ''})", "qty": 1, "rate": b["total"], "amount": b["total"]}]

    # Equipment
    eq_ids = json.loads(b.get("equipment", "[]") or "[]")
    if eq_ids:
        for eid in eq_ids:
            eq = conn.execute("SELECT name, hourly_rate FROM equipment WHERE id=?", (eid,)).fetchone()
            if eq:
                cost = eq["hourly_rate"] * hrs
                lines.append({"desc": f"Equipment: {eq['name']} ({hrs}hrs)", "qty": 1, "rate": cost, "amount": cost})

    subtotal = b["total"]
    discount = b.get("discount_amt", 0) or 0
    tax = b.get("tax_amount", 0) or 0
    total = b.get("final_amount", 0) or 0
    name = b.get("guest_name") or "—"
    email = b.get("guest_email") or ""
    phone = b.get("guest_phone") or ""
    org = b.get("guest_org") or ""

    status = "paid" if b.get("pay_status") == "paid" else "issued"

    conn.execute("""INSERT INTO invoices (id, invoice_no, booking_id, invoice_type,
        issued_to_name, issued_to_email, issued_to_phone, issued_to_org,
        subtotal, discount, tax, total, currency, line_items, status, notes, terms)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (iid, inv_no, booking_id, inv_type,
         name, email, phone, org,
         subtotal, discount, tax, total, "GHS", json.dumps(lines), status,
         "", "Payment is due upon approval. Cancellation policy applies."))
    conn.commit()

    inv = conn.execute("SELECT * FROM invoices WHERE id=?", (iid,)).fetchone()
    conn.close()
    return dict(inv)


@router.get("")
async def list_invoices(booking_id: str = None):
    conn = get_db()
    q = "SELECT i.*, b.ref as booking_ref, b.facility_id FROM invoices i JOIN bookings b ON i.booking_id=b.id"
    w, p = [], []
    if booking_id: w.append("i.booking_id=?"); p.append(booking_id)
    if w: q += " WHERE " + " AND ".join(w)
    q += " ORDER BY i.created_at DESC"
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/{iid}")
async def get_invoice(iid: str):
    conn = get_db()
    inv = conn.execute("SELECT i.*, b.ref as booking_ref FROM invoices i JOIN bookings b ON i.booking_id=b.id WHERE i.id=? OR i.invoice_no=?", (iid, iid)).fetchone()
    conn.close()
    if not inv: raise HTTPException(404, "Invoice not found")
    return dict(inv)


@router.post("/generate")
async def generate_invoice(req: Request):
    d = await req.json()
    inv = create_invoice_for_booking(d["booking_id"], d.get("type", "invoice"))
    if not inv: raise HTTPException(404, "Booking not found")
    return inv


@router.get("/{iid}/html", response_class=HTMLResponse)
async def invoice_html(iid: str):
    """Render a printable HTML invoice/receipt."""
    conn = get_db()
    inv = conn.execute("SELECT i.*, b.ref as booking_ref, b.booking_date, b.start_time, b.end_time, f.name as fac_name FROM invoices i JOIN bookings b ON i.booking_id=b.id JOIN facilities f ON b.facility_id=f.id WHERE i.id=? OR i.invoice_no=?", (iid, iid)).fetchone()
    conn.close()
    if not inv: raise HTTPException(404)
    inv = dict(inv)
    lines = json.loads(inv.get("line_items", "[]"))
    is_receipt = inv["invoice_type"] == "receipt"
    doc_title = "RECEIPT" if is_receipt else "INVOICE"
    paid_stamp = '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%) rotate(-30deg);font-size:72px;color:rgba(26,71,49,.08);font-weight:800;letter-spacing:8px">PAID</div>' if inv["status"] == "paid" else ""

    lines_html = ""
    for l in lines:
        lines_html += f'<tr><td style="padding:10px 12px;border-bottom:1px solid #eee">{l["desc"]}</td><td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right">{l["qty"]}</td><td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right">GH\u20b5{l["rate"]:.2f}</td><td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right;font-weight:600">GH\u20b5{l["amount"]:.2f}</td></tr>'

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{doc_title} {inv['invoice_no']}</title>
<style>@media print{{body{{margin:0}}@page{{margin:1cm}}}}body{{font-family:'Segoe UI',sans-serif;color:#1a2318;margin:40px auto;max-width:800px;padding:0 20px}}</style>
</head><body>
<div style="position:relative;background:#fff;padding:40px;border:1px solid #ddd;border-radius:12px">
{paid_stamp}
<div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:36px">
<div><div style="width:48px;height:48px;background:#1a4731;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:20px;font-weight:800;margin-bottom:12px">R</div>
<strong style="font-size:15px">{ORG_SHORT}</strong><br><span style="font-size:12px;color:#666">{ORG_NAME}<br>{ORG_ADDRESS}<br>{ORG_PHONE}</span></div>
<div style="text-align:right"><h1 style="font-size:32px;color:#1a4731;margin:0">{doc_title}</h1>
<p style="font-size:14px;margin:6px 0"><strong>{inv['invoice_no']}</strong></p>
<p style="font-size:12px;color:#888">Issued: {inv['issued_at'][:10] if inv['issued_at'] else '—'}</p>
<p style="font-size:12px;color:#888">Booking: {inv['booking_ref']}</p></div></div>

<div style="display:flex;justify-content:space-between;margin-bottom:28px;padding:16px;background:#f8f8f6;border-radius:8px">
<div><strong style="font-size:11px;text-transform:uppercase;color:#888;letter-spacing:1px">Bill To</strong><br>
<strong>{inv['issued_to_name']}</strong><br>
<span style="font-size:13px;color:#666">{inv['issued_to_org']}<br>{inv['issued_to_email']}<br>{inv['issued_to_phone']}</span></div>
<div style="text-align:right"><strong style="font-size:11px;text-transform:uppercase;color:#888;letter-spacing:1px">Status</strong><br>
<span style="background:{'#dcf0e3' if inv['status']=='paid' else '#fdf3d7'};color:{'#1a4731' if inv['status']=='paid' else '#92400e'};padding:4px 14px;border-radius:20px;font-size:13px;font-weight:600">{inv['status'].upper()}</span></div></div>

<table style="width:100%;border-collapse:collapse;margin-bottom:24px">
<thead><tr style="background:#1a4731;color:#fff"><th style="padding:10px 12px;text-align:left;font-size:12px">Description</th><th style="padding:10px 12px;text-align:right;font-size:12px">Qty</th><th style="padding:10px 12px;text-align:right;font-size:12px">Rate</th><th style="padding:10px 12px;text-align:right;font-size:12px">Amount</th></tr></thead>
<tbody>{lines_html}</tbody></table>

<div style="display:flex;justify-content:flex-end"><div style="width:260px">
<div style="display:flex;justify-content:space-between;padding:6px 0;font-size:14px"><span>Subtotal</span><span>GH\u20b5{inv['subtotal']:.2f}</span></div>
{"<div style='display:flex;justify-content:space-between;padding:6px 0;font-size:14px;color:#1a4731'><span>Discount</span><span>-GH\u20b5" + f"{inv['discount']:.2f}</span></div>" if inv['discount'] > 0 else ""}
{"<div style='display:flex;justify-content:space-between;padding:6px 0;font-size:14px'><span>Tax</span><span>GH\u20b5" + f"{inv['tax']:.2f}</span></div>" if inv['tax'] > 0 else ""}
<div style="display:flex;justify-content:space-between;padding:12px 0;font-size:20px;font-weight:700;border-top:2px solid #1a4731;margin-top:8px"><span>Total</span><span style="color:#1a4731">GH\u20b5{inv['total']:.2f}</span></div>
</div></div>

<div style="margin-top:32px;padding-top:16px;border-top:1px solid #eee;font-size:12px;color:#888">
<p><strong>Terms:</strong> {inv.get('terms','') or 'Payment due upon approval. Cancellation policy applies.'}</p>
<p style="margin-top:8px;text-align:center">Thank you for choosing {ORG_SHORT}!</p>
</div></div>
<div style="text-align:center;margin-top:20px"><button onclick="window.print()" style="background:#1a4731;color:#fff;border:none;padding:12px 32px;border-radius:8px;font-size:14px;cursor:pointer">🖨️ Print / Save as PDF</button></div>
</body></html>"""
