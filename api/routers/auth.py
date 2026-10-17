from datetime import datetime, timedelta
import httpx
import jwt
import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from api.config import settings
from api.deps import get_db, get_current_user
from models import ServerConfig

logger = logging.getLogger("api.auth")
router = APIRouter()

class CodePayload(BaseModel):
    code: str
    redirect_uri: Optional[str] = None

def has_manage_permission(guild: dict) -> bool:
    if guild.get("owner"):
        return True
    try:
        perms = int(guild.get("permissions", "0"))
    except (ValueError, TypeError):
        return False
    return bool(perms & 0x20) or bool(perms & 0x8)

async def fetch_and_save_badge(db: Session, server: ServerConfig):
    """Fetch logo dari API CoC dan simpan ke DB kalau belum ada."""
    if server.clan_badge_url:
        return
        
    token = os.getenv('COC_API_TOKEN')
    if not token:
        return
        
    tag = server.clan_tag.replace('#', '%23')
    url = f"https://cocproxy.royaleapi.dev/v1/clans/{tag}"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url, headers={'Authorization': f'Bearer {token}'})
            if res.status_code == 200:
                data = res.json()
                server.clan_badge_url = data.get('badgeUrls', {}).get('medium')
                db.commit()
    except Exception as e:
        logger.error(f"Gagal fetch badge untuk {server.clan_tag}: {e}")

@router.post("/discord")
async def discord_callback(payload: CodePayload, db: Session = Depends(get_db)):
    if not settings.DISCORD_CLIENT_ID or not settings.DISCORD_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Discord OAuth not configured")

    data = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "client_secret": settings.DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": payload.code,
    }
    if payload.redirect_uri:
        data["redirect_uri"] = payload.redirect_uri

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_res = await client.post(
            "https://discord.com/api/oauth2/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_res.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Discord error: {token_res.text}")
            
        token_data = token_res.json()
        access_token = token_data.get("access_token")

        user_res = await client.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {access_token}"})
        user = user_res.json()

        guilds_res = await client.get("https://discord.com/api/users/@me/guilds", headers={"Authorization": f"Bearer {access_token}"})
        guilds = guilds_res.json()

    admin_guild_ids = [str(g["id"]) for g in guilds if has_manage_permission(g)]

    configured_servers = []
    if admin_guild_ids:
        rows = db.query(ServerConfig).filter(ServerConfig.guild_id.in_(admin_guild_ids)).all()
        for s in rows:
            await fetch_and_save_badge(db, s) # Auto fetch logo
            configured_servers.append({
                "guild_id": s.guild_id,
                "clan_tag": s.clan_tag,
                "clan_badge_url": s.clan_badge_url,
                "tier": s.tier or "free",
                "expired_at": s.expired_at.isoformat() if s.expired_at else None,
            })

    exp = datetime.utcnow() + timedelta(days=settings.JWT_EXPIRE_DAYS)
    jwt_payload = {
        "sub": user["id"],
        "username": user.get("username"),
        "global_name": user.get("global_name"),
        "avatar": user.get("avatar"),
        "servers": [s["guild_id"] for s in configured_servers],
        "exp": exp,
    }
    access_jwt = jwt.encode(jwt_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    return {
        "access_token": access_jwt,
        "user": {"id": user["id"], "username": user.get("username"), "global_name": user.get("global_name"), "avatar": user.get("avatar")},
        "servers": configured_servers,
    }

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    servers = []
    server_ids = user.get("servers") or []
    if server_ids:
        rows = db.query(ServerConfig).filter(ServerConfig.guild_id.in_(server_ids)).all()
        for s in rows:
            await fetch_and_save_badge(db, s) # Auto fetch logo kalau kosong
            servers.append({
                "guild_id": s.guild_id,
                "clan_tag": s.clan_tag,
                "clan_badge_url": s.clan_badge_url,
                "tier": s.tier or "free",
                "expired_at": s.expired_at.isoformat() if s.expired_at else None,
            })

    return {
        "user": {"id": user["sub"], "username": user.get("username"), "global_name": user.get("global_name"), "avatar": user.get("avatar")},
        "servers": servers,
    }
