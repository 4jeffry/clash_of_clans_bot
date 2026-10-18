from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.deps import get_db
from .auth_utils import require_admin

router = APIRouter()

@router.get("/stats")
def get_admin_stats(admin = Depends(require_admin), db: Session = Depends(get_db)):
    total_servers = db.execute(text("SELECT COUNT(*) FROM server_configs")).scalar()
    pro_servers = db.execute(text("SELECT COUNT(*) FROM server_configs WHERE tier = 'pro'")).scalar()
    std_servers = db.execute(text("SELECT COUNT(*) FROM server_configs WHERE tier = 'standard'")).scalar()
    pending_reqs = db.execute(text("SELECT COUNT(*) FROM upgrade_requests WHERE status = 'pending'")).scalar()
    return {
        "total_servers": total_servers or 0,
        "pro_servers": pro_servers or 0,
        "std_servers": std_servers or 0,
        "pending_reqs": pending_reqs or 0
    }
