import os
from fastapi import HTTPException, Depends
from api.deps import get_active_server
from models import ServerConfig

def require_admin(server = Depends(get_active_server)):
    admin_id = os.getenv("ADMIN_DISCORD_ID", "1398959824976478298")
    # server.setup_by isinya Discord ID user yang login (dari token)
    if str(getattr(server, 'setup_by', '')) != admin_id:
        raise HTTPException(status_code=403, detail="Akses ditolak. Khusus Super Admin.")
    return server
