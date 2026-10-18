from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.deps import get_db
from .auth_utils import require_admin

router = APIRouter()

@router.get("/upgrade-requests")
def get_upgrade_requests(admin = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(text("SELECT id, guild_id, clan_tag, requested_tier, created_at FROM upgrade_requests WHERE status = 'pending' ORDER BY created_at ASC")).fetchall()
    return [{"id": r.id, "guild_id": r.guild_id, "clan_tag": r.clan_tag, "tier": r.requested_tier, "date": r.created_at} for r in rows]

@router.delete("/upgrade-requests/{req_id}")
def dismiss_request(req_id: int, admin = Depends(require_admin), db: Session = Depends(get_db)):
    db.execute(text("DELETE FROM upgrade_requests WHERE id = :id"), {"id": req_id})
    db.commit()
    return {"success": True}
