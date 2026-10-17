import os
from datetime import datetime
from fastapi import Depends, Header, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import jwt

from api.config import settings
from models import ServerConfig

DATABASE_URL = os.getenv("DATABASE_URL", "")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.replace("Bearer ", "", 1).strip()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_active_server(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_guild_id: str = Header(None, alias="X-Guild-Id"),
) -> ServerConfig:
    if not x_guild_id:
        raise HTTPException(status_code=400, detail="Missing X-Guild-Id header")
    if x_guild_id not in (user.get("servers") or []):
        raise HTTPException(status_code=403, detail="No access to this server")
    server = db.query(ServerConfig).filter(ServerConfig.guild_id == x_guild_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not configured. Run /setup first.")
    return server


def require_tier(min_tier: str):
    def checker(server: ServerConfig = Depends(get_active_server)) -> ServerConfig:
        ranks = {"free": 0, "standard": 1, "pro": 2}
        effective_tier = server.tier or "free"
        if server.expired_at and server.expired_at < datetime.utcnow():
            effective_tier = "free"
        if ranks.get(effective_tier, 0) < ranks.get(min_tier, 0):
            raise HTTPException(
                status_code=402,
                detail=f"Requires {min_tier} tier or higher. Current: {effective_tier}"
            )
        return server
    return checker
