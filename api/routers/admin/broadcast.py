import os
import httpx
import asyncio
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

async def send_to_channel(client: httpx.AsyncClient, channel_id: str, message: str) -> tuple:
    """Return (success, status_code, error_msg)"""
    try:
        res = await client.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {DISCORD_TOKEN}", "Content-Type": "application/json"},
            json={"content": message},
            timeout=8.0
        )
        if res.status_code == 429:
            retry_after = res.json().get("retry_after", 1)
            await asyncio.sleep(retry_after + 1)
            res = await client.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {DISCORD_TOKEN}", "Content-Type": "application/json"},
                json={"content": message},
                timeout=8.0
            )
        if res.status_code in [200, 201]:
            return (True, res.status_code, None)
        return (False, res.status_code, res.text[:200])
    except Exception as e:
        return (False, 0, str(e)[:200])

async def get_guild_system_channel(client: httpx.AsyncClient, guild_id: str) -> str:
    try:
        res = await client.get(
            f"https://discord.com/api/v10/guilds/{guild_id}",
            headers={"Authorization": f"Bot {DISCORD_TOKEN}"},
            timeout=8.0
        )
        if res.status_code == 200:
            return res.json().get("system_channel_id")
    except Exception:
        pass
    return None

async def send_dm(client: httpx.AsyncClient, owner_id: str, message: str) -> tuple:
    """Return (success, error_msg)"""
    try:
        dm_res = await client.post(
            "https://discord.com/api/v10/users/@me/channels",
            headers={"Authorization": f"Bot {DISCORD_TOKEN}", "Content-Type": "application/json"},
            json={"recipient_id": owner_id},
            timeout=8.0
        )
        if dm_res.status_code not in [200, 201]:
            return (False, f"Cannot open DM: {dm_res.text[:100]}")
        dm_channel = dm_res.json()["id"]
        result = await send_to_channel(client, dm_channel, message)
        return (result[0], result[2])
    except Exception as e:
        return (False, str(e)[:200])

@router.post("/broadcast")
async def send_broadcast(payload: BroadcastPayload, admin = Depends(require_admin), db: Session = Depends(get_db)):
    if not DISCORD_TOKEN:
        raise HTTPException(status_code=500, detail="DISCORD_TOKEN tidak ditemukan di Railway Variables.")
    
    servers = db.execute(text(
        "SELECT guild_id, clan_tag, setup_by, alert_channel_id FROM server_configs"
    )).fetchall()
    
    if not servers:
        return {"success": False, "message": "Belum ada server terdaftar.", "results": []}
    
    results = []
    success = 0
    failed = 0
    
    async with httpx.AsyncClient() as client:
        for srv in servers:
            sent = False
            method = None
            error = None
            
            # Strategi 1: Alert Channel ID
            if srv.alert_channel_id:
                ok, status, err = await send_to_channel(client, srv.alert_channel_id, payload.message)
                if ok:
                    sent = True
                    method = "Alert Channel"
                else:
                    error = f"Alert Channel failed (HTTP {status}): {err}"
            
            # Strategi 2: System Channel
            if not sent:
                sys_chan = await get_guild_system_channel(client, srv.guild_id)
                if sys_chan:
                    ok, status, err = await send_to_channel(client, sys_chan, payload.message)
                    if ok:
                        sent = True
                        method = "System Channel"
                    else:
                        error = (error or "") + f" | System Channel failed (HTTP {status})"
                else:
                    error = (error or "") + " | No system channel"
            
            # Strategi 3: DM Owner
            if not sent and srv.setup_by:
                ok, err = await send_dm(client, srv.setup_by, payload.message)
                if ok:
                    sent = True
                    method = "DM Owner"
                else:
                    error = (error or "") + f" | DM failed: {err}"
            
            if sent:
                success += 1
            else:
                failed += 1
            
            results.append({
                "guild_id": srv.guild_id,
                "clan_tag": srv.clan_tag,
                "sent": sent,
                "method": method or "-",
                "error": error
            })
            
            # Jeda 0.5s biar gak kena rate limit
            await asyncio.sleep(0.5)
    
    return {
        "success": True,
        "total": len(servers),
        "success_count": success,
        "failed_count": failed,
        "results": results
    }
