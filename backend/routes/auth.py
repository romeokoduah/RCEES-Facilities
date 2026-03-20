"""Auth routes: login & register"""
import uuid
import sqlite3
from fastapi import APIRouter, HTTPException, Request
from ..database import get_db, hash_pw

router = APIRouter(prefix="/api/auth", tags=["auth"])

SAFE_FIELDS = ["id", "email", "name", "role", "phone", "department", "organization"]


@router.post("/login")
async def login(req: Request):
    d = await req.json()
    conn = get_db()
    u = conn.execute(
        "SELECT * FROM users WHERE email=? AND is_active=1",
        (d.get("email", "").strip().lower(),)
    ).fetchone()
    if not u or dict(u)["password_hash"] != hash_pw(d.get("password", "")):
        conn.close()
        raise HTTPException(401, "Invalid email or password")
    conn.execute("UPDATE users SET last_login=datetime('now') WHERE id=?", (u["id"],))
    conn.commit()
    conn.close()
    u = dict(u)
    return {"token": u["id"], "user": {k: u[k] for k in SAFE_FIELDS}}


@router.post("/register")
async def register(req: Request):
    d = await req.json()
    uid = str(uuid.uuid4())
    email = d.get("email", "").strip().lower()
    if not email or not d.get("name") or not d.get("password"):
        raise HTTPException(400, "Name, email, and password are required")
    if len(d["password"]) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (id,email,name,password_hash,phone,department,organization) VALUES (?,?,?,?,?,?,?)",
            (uid, email, d["name"].strip(), hash_pw(d["password"]),
             d.get("phone", ""), d.get("department", ""), d.get("organization", ""))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(400, "Email already registered")
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    u = dict(u)
    return {"token": u["id"], "user": {k: u[k] for k in SAFE_FIELDS}}
