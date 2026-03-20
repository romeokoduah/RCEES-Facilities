"""Booking routes: create, list, update, guest lookup, payments"""
import uuid, json, secrets, hashlib, io, csv
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from ..database import get_db
from ..emails import send_booking_confirmation, send_approval_with_payment_link, send_rejection, send_payment_receipt
from ..routes.invoices import create_invoice_for_booking
from ..config import TAX_RATE

router = APIRouter(prefix="/api", tags=["bookings"])


def _bref():
    ch = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return f"RCEES-{''.join(secrets.choice(ch) for _ in range(5))}"


@router.post("/bookings")
async def create_booking(req: Request):
    d = await req.json()
    bid, br = str(uuid.uuid4()), _bref()
    conn = get_db()
    fid = d["facility_id"]; bdate = d["booking_date"]; st = d["start_time"]; et = d["end_time"]

    fac = conn.execute("SELECT * FROM facilities WHERE id=?", (fid,)).fetchone()
    if not fac:
        conn.close(); raise HTTPException(404, "Facility not found")

    # Conflict check
    conflicts = conn.execute(
        """SELECT id FROM bookings WHERE facility_id=? AND booking_date=?
           AND status IN ('pending','confirmed') AND NOT(end_time<=? OR start_time>=?)""",
        (fid, bdate, st, et)
    ).fetchall()
    if conflicts:
        conn.close(); raise HTTPException(409, "Time slot conflict — already reserved")

    # Maintenance check
    maint = conn.execute(
        """SELECT id FROM maintenance WHERE facility_id=?
           AND status IN ('scheduled','in_progress') AND blocks_bookings=1
           AND start_date<=? AND end_date>=?""",
        (fid, bdate, bdate)
    ).fetchall()
    if maint:
        conn.close(); raise HTTPException(409, "Facility under maintenance on this date")

    # Pricing
    sh, eh = int(st.split(":")[0]), int(et.split(":")[0])
    hrs = eh - sh
    if hrs <= 0:
        conn.close(); raise HTTPException(400, "Invalid time range")

    dow = datetime.strptime(bdate, "%Y-%m-%d").weekday()
    wknd = dow >= 5
    rate = fac["hourly_rate"] * (fac["weekend_multiplier"] if wknd else 1)

    if hrs >= 8 and fac["full_day_rate"] > 0:
        sub = fac["full_day_rate"] * (fac["weekend_multiplier"] if wknd else 1)
    elif hrs >= 4 and fac["half_day_rate"] > 0:
        sub = fac["half_day_rate"] * (fac["weekend_multiplier"] if wknd else 1) + max(0, hrs - 4) * rate
    else:
        sub = hrs * rate

    # Equipment
    eq_ids = d.get("equipment", [])
    eq_cost = 0
    for eid in eq_ids:
        eq = conn.execute("SELECT hourly_rate FROM equipment WHERE id=? AND is_active=1", (eid,)).fetchone()
        if eq:
            eq_cost += eq["hourly_rate"] * hrs

    total = round(sub + eq_cost, 2)

    # Discount
    disc_amt = 0
    dc = d.get("discount_code", "").strip().upper()
    if dc:
        disc = conn.execute("SELECT * FROM discounts WHERE code=? AND is_active=1", (dc,)).fetchone()
        if disc:
            dd = dict(disc)
            ok = True
            if dd["min_hours"] > 0 and hrs < dd["min_hours"]:
                ok = False
            if dd["max_uses"] > 0 and dd["times_used"] >= dd["max_uses"]:
                ok = False
            if ok:
                if dd["dtype"] == "percentage":
                    disc_amt = total * (dd["value"] / 100)
                else:
                    disc_amt = min(dd["value"], total)
                if dd["max_discount"] > 0:
                    disc_amt = min(disc_amt, dd["max_discount"])
                conn.execute("UPDATE discounts SET times_used=times_used+1 WHERE id=?", (dd["id"],))

    final = round(max(0, total - disc_amt), 2)
    status = "confirmed" if not fac["requires_approval"] else "pending"

    conn.execute(
        """INSERT INTO bookings
           (id,ref,facility_id,user_id,guest_name,guest_email,guest_phone,guest_org,
            title,description,event_type,booking_date,start_time,end_time,attendees,
            status,total,discount_amt,discount_code,final_amount,
            special_req,equipment,layout,catering,pay_method)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (bid, br, fid, d.get("user_id"), d.get("guest_name", ""), d.get("guest_email", ""),
         d.get("guest_phone", ""), d.get("guest_org", ""),
         d["title"], d.get("description", ""), d.get("event_type", "general"),
         bdate, st, et, d.get("attendees", 1), status, total,
         round(disc_amt, 2), dc if disc_amt > 0 else "", final,
         d.get("special_req", ""), json.dumps(eq_ids),
         d.get("layout", "default"), d.get("catering", 0), d.get("pay_method", ""))
    )
    conn.execute("UPDATE facilities SET total_bookings=total_bookings+1 WHERE id=?", (fid,))
    conn.commit()

    bk = conn.execute(
        """SELECT b.*, f.name as fac_name, c.name as cat_name, c.icon as cat_icon
           FROM bookings b JOIN facilities f ON b.facility_id=f.id
           LEFT JOIN categories c ON f.category_id=c.id WHERE b.id=?""", (bid,)
    ).fetchone()
    conn.close()
    return dict(bk)


@router.get("/bookings/export")
async def export_bookings(date_from: str = None, date_to: str = None, status: str = None):
    """Export bookings as CSV."""
    conn = get_db()
    q = """SELECT b.ref, f.name as facility, b.title, b.guest_name, b.guest_email,
           b.booking_date, b.start_time, b.end_time, b.attendees,
           b.status, b.pay_status, b.total, b.discount_amt, b.final_amount,
           b.pay_method, b.created_at
           FROM bookings b JOIN facilities f ON b.facility_id=f.id"""
    w, p = [], []
    if date_from: w.append("b.booking_date>=?"); p.append(date_from)
    if date_to: w.append("b.booking_date<=?"); p.append(date_to)
    if status: w.append("b.status=?"); p.append(status)
    if w: q += " WHERE " + " AND ".join(w)
    q += " ORDER BY b.booking_date DESC"
    rows = conn.execute(q, p).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Reference", "Facility", "Title", "Guest Name", "Email",
                     "Date", "Start", "End", "Attendees", "Status", "Payment",
                     "Subtotal", "Discount", "Total", "Pay Method", "Created"])
    for r in rows:
        writer.writerow([r["ref"], r["facility"], r["title"], r["guest_name"],
                        r["guest_email"], r["booking_date"], r["start_time"],
                        r["end_time"], r["attendees"], r["status"], r["pay_status"],
                        r["total"], r["discount_amt"], r["final_amount"],
                        r["pay_method"], r["created_at"]])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=rcees_bookings.csv"}
    )


@router.get("/bookings")
async def list_bookings(
    user_id: str = None, facility_id: str = None, status: str = None,
    date_from: str = None, date_to: str = None, search: str = None,
    limit: int = 100, offset: int = 0
):
    conn = get_db()
    q = """SELECT b.*, f.name as fac_name, f.building, c.name as cat_name, c.icon as cat_icon
           FROM bookings b JOIN facilities f ON b.facility_id=f.id
           LEFT JOIN categories c ON f.category_id=c.id"""
    w, p = [], []
    if user_id: w.append("b.user_id=?"); p.append(user_id)
    if facility_id: w.append("b.facility_id=?"); p.append(facility_id)
    if status:
        if "," in status:
            ss = status.split(",")
            w.append(f"b.status IN ({','.join('?' for _ in ss)})")
            p += ss
        else:
            w.append("b.status=?"); p.append(status)
    if date_from: w.append("b.booking_date>=?"); p.append(date_from)
    if date_to: w.append("b.booking_date<=?"); p.append(date_to)
    if search:
        w.append("(b.title LIKE ? OR b.ref LIKE ? OR b.guest_name LIKE ? OR f.name LIKE ?)")
        s = f"%{search}%"; p += [s, s, s, s]
    if w:
        q += " WHERE " + " AND ".join(w)

    count_q = q.split("FROM", 1)
    total = conn.execute("SELECT COUNT(*) as t FROM" + count_q[1], p).fetchone()["t"]
    q += " ORDER BY b.booking_date DESC, b.start_time LIMIT ? OFFSET ?"
    p += [limit, offset]
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows], "total": total}


@router.put("/bookings/{bid}")
async def update_booking(bid: str, req: Request):
    d = await req.json()
    conn = get_db()
    fields, params = [], []
    updatable = [
        "status", "pay_status", "pay_method", "pay_ref",
        "rating", "feedback", "notes", "title", "description",
        "attendees", "special_req"
    ]
    for k in updatable:
        if k in d:
            fields.append(f"{k}=?"); params.append(d[k])
    if not fields:
        conn.close(); return {}
    params.append(bid)
    conn.execute(f"UPDATE bookings SET {','.join(fields)} WHERE id=?", params)
    conn.commit()
    b = conn.execute(
        "SELECT b.*, f.name as fac_name FROM bookings b JOIN facilities f ON b.facility_id=f.id WHERE b.id=?",
        (bid,)
    ).fetchone()
    conn.close()
    return dict(b) if b else {}


@router.get("/bookings/guest/{email}")
async def guest_bookings(email: str):
    conn = get_db()
    rows = conn.execute(
        """SELECT b.*, f.name as fac_name, c.icon as cat_icon
           FROM bookings b JOIN facilities f ON b.facility_id=f.id
           LEFT JOIN categories c ON f.category_id=c.id
           WHERE b.guest_email=? ORDER BY b.booking_date DESC""",
        (email.strip().lower(),)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/bookings/ref/{ref}")
async def lookup_ref(ref: str):
    conn = get_db()
    b = conn.execute(
        """SELECT b.*, f.name as fac_name, f.location as fac_loc
           FROM bookings b JOIN facilities f ON b.facility_id=f.id
           WHERE b.ref=?""", (ref.upper(),)
    ).fetchone()
    conn.close()
    if not b:
        raise HTTPException(404, "Booking reference not found")
    return dict(b)


@router.post("/payments/process")
async def process_payment(req: Request):
    d = await req.json()
    ref = f"PAY-{uuid.uuid4().hex[:12].upper()}"
    conn = get_db()
    conn.execute(
        "UPDATE bookings SET pay_status='paid', pay_ref=?, pay_method=? WHERE id=?",
        (ref, d.get("method", "card"), d["booking_id"])
    )
    conn.commit()
    conn.close()
    return {"success": True, "reference": ref}


@router.post("/bookings/{bid}/approve")
async def approve_booking(bid: str, req: Request):
    """Admin approves a booking — sends email with payment link."""
    d = await req.json()
    conn = get_db()
    # Generate payment token
    token = secrets.token_urlsafe(32)
    conn.execute(
        "UPDATE bookings SET status='confirmed', approved_by=?, approved_at=datetime('now'), payment_token=? WHERE id=?",
        (d.get("approved_by", "admin"), token, bid)
    )
    conn.commit()
    b = conn.execute(
        "SELECT b.*, f.name as fac_name FROM bookings b JOIN facilities f ON b.facility_id=f.id WHERE b.id=?",
        (bid,)
    ).fetchone()
    conn.close()
    if not b:
        raise HTTPException(404, "Booking not found")
    bk = dict(b)
    bk["payment_token"] = token
    try:
        send_approval_with_payment_link(bk, bk.get("fac_name", ""))
    except Exception as e:
        print(f"  ⚠️ Approval email failed: {e}")
    return bk


@router.post("/bookings/{bid}/reject")
async def reject_booking(bid: str, req: Request):
    """Admin rejects a booking — sends rejection email."""
    d = await req.json()
    reason = d.get("reason", "")
    conn = get_db()
    conn.execute("UPDATE bookings SET status='rejected', rejected_reason=? WHERE id=?", (reason, bid))
    conn.commit()
    b = conn.execute(
        "SELECT b.*, f.name as fac_name FROM bookings b JOIN facilities f ON b.facility_id=f.id WHERE b.id=?",
        (bid,)
    ).fetchone()
    conn.close()
    if not b:
        raise HTTPException(404)
    bk = dict(b)
    try:
        send_rejection(bk, bk.get("fac_name", ""), reason)
    except Exception:
        pass
    return bk


@router.post("/bookings/walkin")
async def walkin_booking(req: Request):
    """Create a walk-in booking (on-site, by staff)."""
    d = await req.json()
    d["is_walkin"] = 1
    d["walkin_by"] = d.get("walkin_by", "staff")
    # Walk-ins are auto-confirmed
    bid, br = str(uuid.uuid4()), _bref()
    conn = get_db()
    fid = d["facility_id"]
    fac = conn.execute("SELECT * FROM facilities WHERE id=?", (fid,)).fetchone()
    if not fac:
        conn.close(); raise HTTPException(404, "Facility not found")

    bdate = d["booking_date"]; st = d["start_time"]; et = d["end_time"]
    sh, eh = int(st.split(":")[0]), int(et.split(":")[0])
    hrs = max(eh - sh, 1)

    dow = __import__("datetime").datetime.strptime(bdate, "%Y-%m-%d").weekday()
    wknd = dow >= 5
    rate = fac["hourly_rate"] * (fac["weekend_multiplier"] if wknd else 1)
    total = round(hrs * rate, 2)

    conn.execute(
        """INSERT INTO bookings (id,ref,facility_id,guest_name,guest_email,guest_phone,guest_org,
           title,event_type,booking_date,start_time,end_time,attendees,status,total,final_amount,
           is_walkin,walkin_by,pay_method) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (bid, br, fid, d.get("guest_name","Walk-in"), d.get("guest_email",""),
         d.get("guest_phone",""), d.get("guest_org",""),
         d.get("title","Walk-in Booking"), d.get("event_type","general"),
         bdate, st, et, d.get("attendees",1), "confirmed", total, total,
         1, d.get("walkin_by","staff"), d.get("pay_method","cash"))
    )
    conn.execute("UPDATE facilities SET total_bookings=total_bookings+1 WHERE id=?", (fid,))
    conn.commit()

    bk = conn.execute("SELECT b.*, f.name as fac_name FROM bookings b JOIN facilities f ON b.facility_id=f.id WHERE b.id=?", (bid,)).fetchone()
    conn.close()
    bk_dict = dict(bk)

    # Auto-generate receipt for walk-in
    try:
        create_invoice_for_booking(bid, "receipt")
    except:
        pass

    return bk_dict


@router.get("/bookings/pay/{token}")
async def get_payment_page(token: str):
    """Look up booking by payment token for the payment page."""
    conn = get_db()
    b = conn.execute(
        "SELECT b.*, f.name as fac_name, f.location as fac_loc FROM bookings b JOIN facilities f ON b.facility_id=f.id WHERE b.payment_token=?",
        (token,)
    ).fetchone()
    conn.close()
    if not b:
        raise HTTPException(404, "Invalid or expired payment link")
    return dict(b)
