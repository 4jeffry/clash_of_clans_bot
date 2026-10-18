from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from datetime import datetime, timedelta
from api.deps import get_db, get_current_user
from .auth_utils import require_admin

router = APIRouter()

class TrackPayload(BaseModel):
    path: str
    guild_id: str = None

# Endpoint PUBLIC buat nyatet view (dipanggil dari router Vue)
@router.post("/track")
def track_view(payload: TrackPayload, request: Request, db: Session = Depends(get_db)):
    try:
        # Coba ambil user id dari token (kalau ada)
        auth = request.headers.get("Authorization", "")
        user_id = None
        if auth.startswith("Bearer "):
            from api.deps import get_current_user
            from api.config import settings
            import jwt
            try:
                token = auth.replace("Bearer ", "").strip()
                decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
                user_id = str(decoded.get("id") or decoded.get("user_id") or "")
            except Exception:
                pass
        
        db.execute(
            text("INSERT INTO analytics_events (path, user_id, guild_id) VALUES (:path, :uid, :gid)"),
            {"path": payload.path, "uid": user_id, "gid": payload.guild_id}
        )
        db.commit()
    except Exception:
        pass # Sengaja dibiarin silent, gak boleh ganggu UX user
    return {"success": True}

# Endpoint ADMIN buat baca stats
@router.get("/analytics/overview")
def get_analytics_overview(admin = Depends(require_admin), db: Session = Depends(get_db)):
    # 1. Total Views 30 hari terakhir
    total_views = db.execute(text("SELECT COUNT(*) FROM analytics_events WHERE created_at > NOW() - INTERVAL '30 days'")).scalar() or 0
    
    # 2. Unique Users 30 hari terakhir
    unique_users = db.execute(text("SELECT COUNT(DISTINCT user_id) FROM analytics_events WHERE user_id IS NOT NULL AND created_at > NOW() - INTERVAL '30 days'")).scalar() or 0
    
    # 3. Views per Hari (7 hari terakhir untuk grafik)
    daily_rows = db.execute(text("""
        SELECT DATE(created_at) as tgl, COUNT(*) as jml 
        FROM analytics_events 
        WHERE created_at > NOW() - INTERVAL '7 days'
        GROUP BY DATE(created_at) 
        ORDER BY tgl ASC
    """)).fetchall()
    
    daily_labels = [r.tgl.strftime('%d %b') for r in daily_rows]
    daily_data = [r.jml for r in daily_rows]
    
    # 4. Top Pages 30 hari
    top_pages_rows = db.execute(text("""
        SELECT path, COUNT(*) as jml 
        FROM analytics_events 
        WHERE created_at > NOW() - INTERVAL '30 days'
        GROUP BY path 
        ORDER BY jml DESC 
        LIMIT 5
    """)).fetchall()
    
    top_pages = [{"path": r.path, "views": r.jml} for r in top_pages_rows]
    
    return {
        "total_views": total_views,
        "unique_users": unique_users,
        "daily_trend": {"labels": daily_labels, "data": daily_data},
        "top_pages": top_pages
    }
