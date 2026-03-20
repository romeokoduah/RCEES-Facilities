"""Facility routes: list, detail, create, update, media upload, time slots"""
import uuid, json, mimetypes
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from ..database import get_db
from ..config import UPLOAD_DIR

router = APIRouter(prefix="/api", tags=["facilities"])


@router.get("/categories")
async def list_categories():
    conn = get_db()
    rows = conn.execute("SELECT * FROM categories ORDER BY sort_order").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/facilities")
async def list_facilities(category: str = None, active_only: bool = True, search: str = None):
    conn = get_db()
    q = """SELECT f.*, c.name as cat_name, c.icon as cat_icon, c.color as cat_color
           FROM facilities f LEFT JOIN categories c ON f.category_id=c.id"""
    w, p = [], []
    if active_only:
        w.append("f.is_active=1")
    if category:
        w.append("f.category_id=?"); p.append(category)
    if search:
        w.append("(f.name LIKE ? OR f.description LIKE ? OR f.building LIKE ?)")
        s = f"%{search}%"; p += [s, s, s]
    if w:
        q += " WHERE " + " AND ".join(w)
    q += " ORDER BY f.name"
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/facilities/{fid}")
async def get_facility(fid: str):
    conn = get_db()
    f = conn.execute(
        """SELECT f.*, c.name as cat_name, c.icon as cat_icon, c.color as cat_color
           FROM facilities f LEFT JOIN categories c ON f.category_id=c.id
           WHERE f.id=? OR f.slug=?""", (fid, fid)
    ).fetchone()
    if not f:
        conn.close(); raise HTTPException(404, "Facility not found")
    reviews = conn.execute(
        """SELECT r.*, u.name as uname FROM reviews r
           LEFT JOIN users u ON r.user_id=u.id
           WHERE r.facility_id=? AND r.is_visible=1
           ORDER BY r.created_at DESC LIMIT 10""", (f["id"],)
    ).fetchall()
    conn.close()
    res = dict(f)
    res["reviews"] = [dict(r) for r in reviews]
    return res


@router.post("/facilities")
async def create_facility(req: Request):
    d = await req.json()
    fid = str(uuid.uuid4())
    slug = ''.join(c for c in d["name"].lower().replace(" ", "-").replace("&", "and") if c.isalnum() or c == '-')
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO facilities
               (id,name,slug,category_id,capacity,description,short_desc,amenities,
                hourly_rate,half_day_rate,full_day_rate,location,building,floor,
                requires_approval,min_hours,rules,contact_person,contact_phone,media)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, d["name"], slug, d.get("category_id", ""), d.get("capacity", 10),
             d.get("description", ""), d.get("short_desc", ""),
             json.dumps(d.get("amenities", [])),
             d.get("hourly_rate", 0), d.get("half_day_rate", 0), d.get("full_day_rate", 0),
             d.get("location", ""), d.get("building", ""), d.get("floor", ""),
             d.get("requires_approval", 0), d.get("min_hours", 1),
             d.get("rules", ""), d.get("contact_person", ""), d.get("contact_phone", ""),
             json.dumps(d.get("media", [])))
        )
        conn.commit()
    except Exception:
        conn.close(); raise HTTPException(400, "Facility already exists")
    f = conn.execute("SELECT * FROM facilities WHERE id=?", (fid,)).fetchone()
    conn.close()
    return dict(f)


@router.put("/facilities/{fid}")
async def update_facility(fid: str, req: Request):
    d = await req.json()
    conn = get_db()
    fields, params = [], []
    updatable = [
        "name", "category_id", "capacity", "description", "short_desc", "amenities",
        "hourly_rate", "half_day_rate", "full_day_rate", "weekend_multiplier",
        "location", "building", "floor", "is_active", "requires_approval",
        "min_hours", "max_hours", "rules", "contact_person", "contact_phone",
        "media", "op_hours", "blocked_days"
    ]
    for k in updatable:
        if k in d:
            fields.append(f"{k}=?")
            v = d[k]
            params.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if fields:
        params.append(fid)
        conn.execute(f"UPDATE facilities SET {','.join(fields)} WHERE id=?", params)
        conn.commit()
    f = conn.execute("SELECT * FROM facilities WHERE id=?", (fid,)).fetchone()
    conn.close()
    return dict(f) if f else {}


@router.post("/facilities/{fid}/media")
async def upload_media(fid: str, file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    allowed = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm', '.mov'}
    if ext not in allowed:
        raise HTTPException(400, f"File type {ext} not allowed")
    fname = f"{fid}_{uuid.uuid4().hex[:8]}{ext}"
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 50MB)")
    fpath = UPLOAD_DIR / "facilities" / fname
    with open(fpath, "wb") as f:
        f.write(content)
    url = f"/uploads/facilities/{fname}"
    conn = get_db()
    fac = conn.execute("SELECT media FROM facilities WHERE id=?", (fid,)).fetchone()
    if fac:
        ml = json.loads(fac["media"] or "[]")
        mime = mimetypes.guess_type(file.filename)[0] or "image/jpeg"
        ml.append({"url": url, "type": "video" if "video" in mime else "image", "name": file.filename})
        conn.execute("UPDATE facilities SET media=? WHERE id=?", (json.dumps(ml), fid))
        conn.commit()
    conn.close()
    return {"url": url, "filename": fname}


@router.get("/facilities/{fid}/slots")
async def get_slots(fid: str, date: str):
    conn = get_db()
    fac = conn.execute("SELECT * FROM facilities WHERE id=? OR slug=?", (fid, fid)).fetchone()
    if not fac:
        conn.close(); raise HTTPException(404, "Facility not found")
    fid_real = fac["id"]
    oh = json.loads(fac["op_hours"] or '{"start":7,"end":21}')

    bookings = conn.execute(
        "SELECT start_time, end_time FROM bookings WHERE facility_id=? AND booking_date=? AND status IN ('pending','confirmed')",
        (fid_real, date)
    ).fetchall()
    maint = conn.execute(
        """SELECT start_time, end_time FROM maintenance
           WHERE facility_id=? AND status IN ('scheduled','in_progress')
           AND start_date<=? AND end_date>=? AND blocks_bookings=1""",
        (fid_real, date, date)
    ).fetchall()
    conn.close()

    booked = [(b["start_time"], b["end_time"]) for b in bookings]
    maint_ranges = [(m["start_time"], m["end_time"]) for m in maint]
    dow = datetime.strptime(date, "%Y-%m-%d").weekday()
    is_weekend = dow >= 5
    blocked_days = json.loads(fac["blocked_days"] or "[]")
    day_name = datetime.strptime(date, "%Y-%m-%d").strftime("%A").lower()
    is_blocked = day_name in [d.lower() for d in blocked_days]

    slots = []
    for h in range(oh.get("start", 7), oh.get("end", 21)):
        s, e = f"{h:02d}:00", f"{h+1:02d}:00"
        status = "available"
        if is_blocked:
            status = "blocked"
        else:
            for ms, me in maint_ranges:
                if not (e <= ms or s >= me):
                    status = "maintenance"; break
            if status == "available":
                for bs, be in booked:
                    if not (e <= bs or s >= be):
                        status = "booked"; break
        rate = fac["hourly_rate"] * (fac["weekend_multiplier"] if is_weekend else 1)
        slots.append({
            "start": s, "end": e,
            "available": status == "available",
            "status": status,
            "rate": round(rate, 2),
            "is_weekend": is_weekend,
        })
    return {"facility_id": fid_real, "date": date, "is_weekend": is_weekend, "is_blocked": is_blocked, "slots": slots}
