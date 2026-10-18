from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from datetime import datetime, timedelta
from api.deps import get_db
from .auth_utils import require_admin

router = APIRouter()

class UpdateServerPayload(BaseModel):
    tier: str
    ai_credits: int
    days_added: int = 30

@router.get("/servers")
def get_all_servers(admin = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT guild_id, clan_tag, tier, expired_at, ai_credits, clan_badge_url, setup_by FROM server_configs ORDER BY created_at DESC")
    ).fetchall()
    return [
        {
            "guild_id": r.guild_id,
            "clan_tag": r.clan_tag,
            "tier": r.tier or 'free',
            "expired_at": r.expired_at,
            "ai_credits": r.ai_credits or 0,
            "clan_badge_url": r.clan_badge_url or '',
            "setup_by": r.setup_by
        } for r in rows
    ]

@router.put("/servers/{guild_id}")
def update_server(guild_id: str, payload: UpdateServerPayload, admin = Depends(require_admin), db: Session = Depends(get_db)):
    server = db.execute(text("SELECT expired_at FROM server_configs WHERE guild_id = :gid"), {"gid": guild_id}).fetchone()
    if not server:
        raise HTTPException(status_code=404, detail="Server tidak ditemukan")
    current_expiry = server.expired_at if server.expired_at else datetime.utcnow()
    if current_expiry < datetime.utcnow():
        current_expiry = datetime.utcnow()
    new_expiry = current_expiry + timedelta(days=payload.days_added)
    db.execute(
        text("UPDATE server_configs SET tier = :tier, ai_credits = :credits, expired_at = :exp WHERE guild_id = :gid"),
        {"tier": payload.tier, "credits": payload.ai_credits, "exp": new_expiry, "gid": guild_id}
    )
    db.commit()
    return {"success": True}
