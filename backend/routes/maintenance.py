"""Maintenance routes: schedule, list, update"""
import uuid
from fastapi import APIRouter, HTTPException, Request
from ..database import get_db

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


@router.get("")
async def list_maintenance(facility_id: str = None, status: str = None):
    conn = get_db()
    q = "SELECT m.*, f.name as fac_name FROM maintenance m JOIN facilities f ON m.facility_id=f.id"
    w, p = [], []
    if facility_id: w.append("m.facility_id=?"); p.append(facility_id)
    if status: w.append("m.status=?"); p.append(status)
    if w: q += " WHERE " + " AND ".join(w)
    q += " ORDER BY m.start_date DESC"
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("")
async def create_maintenance(req: Request):
    d = await req.json()
    mid = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        """INSERT INTO maintenance
           (id,facility_id,title,description,mtype,priority,start_date,end_date,
            start_time,end_time,assigned_to,vendor,cost_est,blocks_bookings,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (mid, d["facility_id"], d["title"], d.get("description", ""),
         d.get("mtype", "routine"), d.get("priority", "medium"),
         d["start_date"], d["end_date"],
         d.get("start_time", "00:00"), d.get("end_time", "23:59"),
         d.get("assigned_to", ""), d.get("vendor", ""),
         d.get("cost_est", 0), d.get("blocks_bookings", 1), d.get("notes", ""))
    )
    conn.commit()
    m = conn.execute(
        "SELECT m.*, f.name as fac_name FROM maintenance m JOIN facilities f ON m.facility_id=f.id WHERE m.id=?",
        (mid,)
    ).fetchone()
    conn.close()
    return dict(m)


@router.put("/{mid}")
async def update_maintenance(mid: str, req: Request):
    d = await req.json()
    conn = get_db()
    fields, params = [], []
    for k in ["status", "title", "description", "mtype", "priority",
              "start_date", "end_date", "assigned_to", "vendor",
              "cost_est", "actual_cost", "blocks_bookings", "notes"]:
        if k in d:
            fields.append(f"{k}=?"); params.append(d[k])
    if "status" in d and d["status"] == "completed":
        fields.append("completed_at=datetime('now')")
    if not fields:
        conn.close(); return {}
    params.append(mid)
    conn.execute(f"UPDATE maintenance SET {','.join(fields)} WHERE id=?", params)
    conn.commit()
    m = conn.execute(
        "SELECT m.*, f.name as fac_name FROM maintenance m JOIN facilities f ON m.facility_id=f.id WHERE m.id=?",
        (mid,)
    ).fetchone()
    conn.close()
    return dict(m) if m else {}
