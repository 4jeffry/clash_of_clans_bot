from datetime import datetime, timedelta
import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.config import settings
from api.deps import get_db, get_current_user
from models import ServerConfig

router = APIRouter()


class CodePayload(BaseModel):
    code: str


def has_manage_permission(guild: dict) -> bool:
    if guild.get("owner"):
        return True
    try:
        perms = int(guild.get("permissions", "0"))
    except (ValueError, TypeError):
        return False
    # MANAGE_GUILD (0x20) or ADMINISTRATOR (0x8)
    return bool(perms & 0x20) or bool(perms & 0x8)


@router.post("/discord")
async def discord_callback(payload: CodePayload, db: Session = Depends(get_db)):
    if not settings.DISCORD_CLIENT_ID or not settings.DISCORD_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Discord OAuth not configured")

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_res = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": settings.DISCORD_CLIENT_ID,
                "client_secret": settings.DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": payload.code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Discord token exchange failed")
        token_data = token_res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token from Discord")

        user_res = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch Discord user")
        user = user_res.json()

        guilds_res = await client.get(
            "https://discord.com/api/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if guilds_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user guilds")
        guilds = guilds_res.json()

    admin_guild_ids = [str(g["id"]) for g in guilds if has_manage_permission(g)]

    configured_servers = []
    if admin_guild_ids:
        rows = (
            db.query(ServerConfig)
            .filter(ServerConfig.guild_id.in_(admin_guild_ids))
            .all()
        )
        configured_servers = [
            {
                "guild_id": s.guild_id,
                "clan_tag": s.clan_tag,
                "tier": s.tier or "free",
                "expired_at": s.expired_at.isoformat() if s.expired_at else None,
            }
            for s in rows
        ]

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
        "user": {
            "id": user["id"],
            "username": user.get("username"),
            "global_name": user.get("global_name"),
            "avatar": user.get("avatar"),
        },
        "servers": configured_servers,
    }


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    servers = []
    server_ids = user.get("servers") or []
    if server_ids:
        rows = db.query(ServerConfig).filter(ServerConfig.guild_id.in_(server_ids)).all()
        servers = [
            {
                "guild_id": s.guild_id,
                "clan_tag": s.clan_tag,
                "tier": s.tier or "free",
                "expired_at": s.expired_at.isoformat() if s.expired_at else None,
            }
            for s in rows
        ]

    return {
        "user": {
            "id": user["sub"],
            "username": user.get("username"),
            "global_name": user.get("global_name"),
            "avatar": user.get("avatar"),
        },
        "servers": servers,
    }
