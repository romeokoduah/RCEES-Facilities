"""Discount routes: list, create, update, validate"""
import uuid
from fastapi import APIRouter, HTTPException, Request
from ..database import get_db

router = APIRouter(prefix="/api/discounts", tags=["discounts"])


@router.get("")
async def list_discounts():
    conn = get_db()
    rows = conn.execute("SELECT * FROM discounts ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("")
async def create_discount(req: Request):
    d = await req.json()
    did = str(uuid.uuid4())
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO discounts
               (id,code,name,description,dtype,value,min_hours,max_discount,max_uses,is_active)
               VALUES (?,?,?,?,?,?,?,?,?,1)""",
            (did, d["code"].upper(), d["name"], d.get("description", ""),
             d.get("dtype", "percentage"), d["value"],
             d.get("min_hours", 0), d.get("max_discount", 0), d.get("max_uses", 0))
        )
        conn.commit()
    except Exception:
        conn.close(); raise HTTPException(400, "Discount code already exists")
    r = conn.execute("SELECT * FROM discounts WHERE id=?", (did,)).fetchone()
    conn.close()
    return dict(r)


@router.put("/{did}")
async def update_discount(did: str, req: Request):
    d = await req.json()
    conn = get_db()
    fields, params = [], []
    for k in ["name", "description", "value", "min_hours", "max_discount", "max_uses", "is_active"]:
        if k in d:
            fields.append(f"{k}=?"); params.append(d[k])
    if not fields:
        conn.close(); return {"ok": True}
    params.append(did)
    conn.execute(f"UPDATE discounts SET {','.join(fields)} WHERE id=?", params)
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/validate")
async def validate_discount(req: Request):
    d = await req.json()
    code = d.get("code", "").strip().upper()
    hrs = d.get("hours", 1)
    amt = d.get("amount", 0)
    conn = get_db()
    disc = conn.execute("SELECT * FROM discounts WHERE code=? AND is_active=1", (code,)).fetchone()
    conn.close()
    if not disc:
        return {"valid": False, "message": "Invalid discount code"}
    dd = dict(disc)
    if dd["max_uses"] > 0 and dd["times_used"] >= dd["max_uses"]:
        return {"valid": False, "message": "Code fully redeemed"}
    if dd["min_hours"] > 0 and hrs < dd["min_hours"]:
        return {"valid": False, "message": f"Minimum {dd['min_hours']} hours required"}
    if dd["dtype"] == "percentage":
        disc_amt = amt * (dd["value"] / 100)
    else:
        disc_amt = min(dd["value"], amt)
    if dd["max_discount"] > 0:
        disc_amt = min(disc_amt, dd["max_discount"])
    return {"valid": True, "discount": dd, "calculated": round(disc_amt, 2)}
