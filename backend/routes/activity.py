"""Activity log routes"""
import uuid
from fastapi import APIRouter, Request
from ..database import get_db

router = APIRouter(prefix="/api/activity", tags=["activity"])


def log_activity(action, entity_type="", entity_id="", user_id="", user_name="", details=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO activity_log (id, action, entity_type, entity_id, user_id, user_name, details) VALUES (?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), action, entity_type, entity_id, user_id, user_name, details)
    )
    conn.commit()
    conn.close()


@router.get("")
async def list_activity(limit: int = 50, entity_type: str = None):
    conn = get_db()
    q = "SELECT * FROM activity_log"
    w, p = [], []
    if entity_type:
        w.append("entity_type=?"); p.append(entity_type)
    if w:
        q += " WHERE " + " AND ".join(w)
    q += " ORDER BY created_at DESC LIMIT ?"
    p.append(limit)
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]
