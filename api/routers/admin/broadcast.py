import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from api.deps import get_db
from .auth_utils import require_admin

router = APIRouter()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

class BroadcastPayload(BaseModel):
    message: str

@router.post("/broadcast")
async def send_broadcast(payload: BroadcastPayload, admin = Depends(require_admin), db: Session = Depends(get_db)):
    if not DISCORD_TOKEN:
        raise HTTPException(status_code=500, detail="DISCORD_TOKEN tidak ditemukan di Railway Variables.")
        
    channels = db.execute(text("SELECT alert_channel_id FROM server_configs WHERE alert_channel_id IS NOT NULL AND alert_channel_id != ''")).fetchall()
    if not channels:
        return {"success": True, "sent": 0, "message": "Tidak ada channel notifikasi yang terdaftar."}

    success_count = 0
    async with httpx.AsyncClient() as client:
        for chan in channels:
            try:
                res = await client.post(
                    f"https://discord.com/api/v10/channels/{chan.alert_channel_id}/messages",
                    headers={"Authorization": f"Bot {DISCORD_TOKEN}", "Content-Type": "application/json"},
                    json={"content": payload.message}
                )
                if res.status_code in [200, 201]:
                    success_count += 1
            except Exception:
                pass

    return {"success": True, "sent": success_count, "total": len(channels)}
