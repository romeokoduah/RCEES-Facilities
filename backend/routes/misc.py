"""Remaining routes: equipment, users, reviews, analytics"""
import uuid
from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Request
from ..database import get_db

equipment_router = APIRouter(prefix="/api/equipment", tags=["equipment"])
users_router = APIRouter(prefix="/api/users", tags=["users"])
reviews_router = APIRouter(prefix="/api/reviews", tags=["reviews"])
analytics_router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ═══════ Equipment ═══════
@equipment_router.get("")
async def list_equipment():
    conn = get_db()
    rows = conn.execute("SELECT * FROM equipment WHERE is_active=1 ORDER BY category, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════ Users ═══════
@users_router.get("")
async def list_users(search: str = None):
    conn = get_db()
    q = "SELECT id,email,name,role,phone,department,organization,is_active,created_at,last_login FROM users"
    w, p = [], []
    if search:
        w.append("(name LIKE ? OR email LIKE ? OR department LIKE ?)")
        s = f"%{search}%"; p += [s, s, s]
    if w:
        q += " WHERE " + " AND ".join(w)
    q += " ORDER BY created_at DESC"
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@users_router.put("/{uid}")
async def update_user(uid: str, req: Request):
    d = await req.json()
    conn = get_db()
    fields, params = [], []
    for k in ["name", "role", "phone", "department", "organization", "is_active"]:
        if k in d:
            fields.append(f"{k}=?"); params.append(d[k])
    if fields:
        params.append(uid)
        conn.execute(f"UPDATE users SET {','.join(fields)} WHERE id=?", params)
        conn.commit()
    conn.close()
    return {"ok": True}


# ═══════ Reviews ═══════
@reviews_router.post("")
async def create_review(req: Request):
    d = await req.json()
    rid = str(uuid.uuid4())
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO reviews (id,booking_id,facility_id,user_id,guest_name,rating,comment) VALUES (?,?,?,?,?,?,?)",
            (rid, d["booking_id"], d["facility_id"], d.get("user_id"),
             d.get("guest_name", ""), d["rating"], d.get("comment", ""))
        )
        conn.execute("UPDATE bookings SET rating=?, feedback=? WHERE id=?",
                     (d["rating"], d.get("comment", ""), d["booking_id"]))
        avg = conn.execute(
            "SELECT AVG(rating) as v FROM reviews WHERE facility_id=? AND is_visible=1",
            (d["facility_id"],)
        ).fetchone()
        if avg and avg["v"]:
            conn.execute("UPDATE facilities SET avg_rating=? WHERE id=?",
                        (round(avg["v"], 1), d["facility_id"]))
        conn.commit()
    except Exception:
        conn.close()
        raise HTTPException(400, "Review already exists for this booking")
    conn.close()
    return {"ok": True}


# ═══════ Analytics ═══════
@analytics_router.get("/overview")
async def analytics_overview():
    conn = get_db()
    td = date.today().isoformat()
    ms = date.today().replace(day=1).isoformat()

    s = {}
    s["total_facilities"] = conn.execute("SELECT COUNT(*) as c FROM facilities WHERE is_active=1").fetchone()["c"]
    s["total_bookings"] = conn.execute("SELECT COUNT(*) as c FROM bookings").fetchone()["c"]
    s["today_bookings"] = conn.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE booking_date=? AND status IN ('confirmed','pending')", (td,)
    ).fetchone()["c"]
    s["pending"] = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE status='pending'").fetchone()["c"]
    s["upcoming"] = conn.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE booking_date>=? AND status='confirmed'", (td,)
    ).fetchone()["c"]
    s["month_rev"] = conn.execute(
        "SELECT COALESCE(SUM(final_amount),0) as v FROM bookings WHERE booking_date>=? AND pay_status='paid'", (ms,)
    ).fetchone()["v"]
    s["total_rev"] = conn.execute(
        "SELECT COALESCE(SUM(final_amount),0) as v FROM bookings WHERE pay_status='paid'"
    ).fetchone()["v"]
    s["total_users"] = conn.execute("SELECT COUNT(*) as c FROM users WHERE role!='admin'").fetchone()["c"]
    s["active_maint"] = conn.execute(
        "SELECT COUNT(*) as c FROM maintenance WHERE status IN ('scheduled','in_progress')"
    ).fetchone()["c"]

    # Occupancy
    tp = max(s["total_facilities"] * 14 * 30, 1)
    bh = conn.execute(
        """SELECT COALESCE(SUM(CAST(substr(end_time,1,2) AS INT)-CAST(substr(start_time,1,2) AS INT)),0) as h
           FROM bookings WHERE booking_date>=? AND status IN ('confirmed','completed')""", (ms,)
    ).fetchone()["h"]
    s["occupancy"] = round((bh / tp) * 100, 1)

    # Popular facilities
    s["popular"] = [dict(r) for r in conn.execute(
        """SELECT f.name, f.id, COUNT(b.id) as cnt, COALESCE(SUM(b.final_amount),0) as rev
           FROM bookings b JOIN facilities f ON b.facility_id=f.id
           WHERE b.status IN ('confirmed','completed')
           GROUP BY f.id ORDER BY cnt DESC LIMIT 6"""
    ).fetchall()]

    # Monthly trends (6 months)
    trends = []
    for i in range(5, -1, -1):
        dd = date.today().replace(day=1) - timedelta(days=30 * i)
        m1 = dd.replace(day=1).isoformat()
        m2 = (dd.replace(day=28) + timedelta(days=4)).replace(day=1).isoformat()
        cnt = conn.execute(
            "SELECT COUNT(*) as c FROM bookings WHERE booking_date>=? AND booking_date<?", (m1, m2)
        ).fetchone()["c"]
        rev = conn.execute(
            "SELECT COALESCE(SUM(final_amount),0) as v FROM bookings WHERE booking_date>=? AND booking_date<? AND pay_status='paid'",
            (m1, m2)
        ).fetchone()["v"]
        trends.append({"month": dd.strftime("%b %Y"), "short": dd.strftime("%b"), "bookings": cnt, "revenue": round(rev, 2)})
    s["trends"] = trends

    # Recent bookings
    s["recent"] = [dict(r) for r in conn.execute(
        """SELECT b.*, f.name as fac_name, c.icon as cat_icon
           FROM bookings b JOIN facilities f ON b.facility_id=f.id
           LEFT JOIN categories c ON f.category_id=c.id
           ORDER BY b.created_at DESC LIMIT 15"""
    ).fetchall()]

    # Today's schedule
    s["today_schedule"] = [dict(r) for r in conn.execute(
        """SELECT b.*, f.name as fac_name, c.icon as cat_icon
           FROM bookings b JOIN facilities f ON b.facility_id=f.id
           LEFT JOIN categories c ON f.category_id=c.id
           WHERE b.booking_date=? AND b.status IN ('confirmed','pending')
           ORDER BY b.start_time""", (td,)
    ).fetchall()]

    conn.close()
    return s


@analytics_router.get("/emails")
async def email_log():
    conn = get_db()
    rows = conn.execute("SELECT * FROM email_log ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]
