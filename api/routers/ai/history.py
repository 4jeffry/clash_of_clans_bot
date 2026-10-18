from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.deps import get_active_server, get_db
from .utils import check_pro_tier

router = APIRouter()

@router.get("/history")
def get_ai_history(server = Depends(get_active_server), db: Session = Depends(get_db)):
    check_pro_tier(server)
    rows = db.execute(
        text("SELECT id, feature_type, created_at, result_narrative FROM ai_reports WHERE guild_id = :gid ORDER BY created_at DESC LIMIT 20"),
        {"gid": server.guild_id}
    ).fetchall()
    return [{"id": str(r[0]), "type": r[1], "date": r[2], "snippet": r[3][:100] + "..." if len(r[3]) > 100 else r[3]} for r in rows]

@router.get("/history/{report_id}")
def get_ai_history_detail(report_id: str, server = Depends(get_active_server), db: Session = Depends(get_db)):
    check_pro_tier(server)
    row = db.execute(
        text("SELECT id, feature_type, input_data, result_narrative, created_at FROM ai_reports WHERE id = :rid AND guild_id = :gid"),
        {"rid": report_id, "gid": server.guild_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Report tidak ditemukan")
    return {"id": str(row[0]), "type": row[1], "raw_data": row[2], "narrative": row[3], "date": row[4]}

@router.delete("/history/{report_id}")
def delete_ai_history(report_id: str, server = Depends(get_active_server), db: Session = Depends(get_db)):
    check_pro_tier(server)
    try:
        res = db.execute(
            text("DELETE FROM ai_reports WHERE id = :rid AND guild_id = :gid"),
            {"rid": report_id, "gid": server.guild_id}
        )
        db.commit()
        if res.rowcount == 0:
            raise HTTPException(status_code=404, detail="Report tidak ditemukan")
        return {"success": True, "message": "Report berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
