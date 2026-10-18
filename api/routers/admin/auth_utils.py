import os
from fastapi import HTTPException, Depends
from api.deps import get_active_server, get_current_user
from models import ServerConfig

def require_admin(
    user: dict = Depends(get_current_user),
    server: ServerConfig = Depends(get_active_server)
):
    admin_id = os.getenv("ADMIN_DISCORD_ID", "1398959824976478298")
    user_id = str(
        user.get("id") or 
        user.get("user_id") or 
        user.get("discord_id") or 
        user.get("sub") or 
        ""
    )
    if user_id != admin_id:
        raise HTTPException(
            status_code=403, 
            detail=f"Akses ditolak. ID terdeteksi: {user_id}"
        )
    return server
