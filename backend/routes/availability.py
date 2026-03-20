"""Availability management routes"""
import uuid, json
from fastapi import APIRouter, HTTPException, Request
from ..database import get_db

router = APIRouter(prefix="/api/availability", tags=["availability"])


@router.get("/rules")
async def list_rules(facility_id: str = None):
    conn = get_db()
    q = """SELECT a.*, f.name as fac_name FROM availability_rules a
           LEFT JOIN facilities f ON a.facility_id=f.id"""
    w, p = [], []
    if facility_id:
        w.append("a.facility_id=?"); p.append(facility_id)
    if w:
        q += " WHERE " + " AND ".join(w)
    q += " ORDER BY a.created_at DESC"
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/rules")
async def create_rule(req: Request):
    d = await req.json()
    rid = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        """INSERT INTO availability_rules
           (id, facility_id, rule_type, date, day_of_week, start_time, end_time,
            is_available, reason, created_by)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (rid, d.get("facility_id"), d["rule_type"],
         d.get("date"), d.get("day_of_week"),
         d.get("start_time", "00:00"), d.get("end_time", "23:59"),
         d.get("is_available", 0), d.get("reason", ""), d.get("created_by", "admin"))
    )
    conn.commit()
    r = conn.execute("SELECT * FROM availability_rules WHERE id=?", (rid,)).fetchone()
    conn.close()
    return dict(r)


@router.delete("/rules/{rid}")
async def delete_rule(rid: str):
    conn = get_db()
    conn.execute("DELETE FROM availability_rules WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/bulk")
async def bulk_set_availability(req: Request):
    """Set availability for multiple dates at once."""
    d = await req.json()
    facility_id = d["facility_id"]
    dates = d.get("dates", [])
    rule_type = d.get("rule_type", "block_date")
    reason = d.get("reason", "")
    start_time = d.get("start_time", "00:00")
    end_time = d.get("end_time", "23:59")
    created_by = d.get("created_by", "admin")

    conn = get_db()
    created = []
    for date in dates:
        rid = str(uuid.uuid4())
        try:
            conn.execute(
                """INSERT INTO availability_rules
                   (id, facility_id, rule_type, date, start_time, end_time,
                    is_available, reason, created_by)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (rid, facility_id, rule_type, date, start_time, end_time,
                 0, reason, created_by)
            )
            created.append(rid)
        except Exception:
            pass
    conn.commit()
    conn.close()
    return {"created": len(created)}
