import json
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

def check_pro_tier(server):
    # Ngecek tier dari server config. Kalau bukan 'pro', langsung tolak
    if getattr(server, 'tier', 'free') != 'pro':
        raise HTTPException(status_code=403, detail="Fitur ini khusus pengguna PRO. Silakan upgrade.")

def disable_prepare(db: Session):
    try:
        if hasattr(db, 'connection') and hasattr(db.connection(), 'connection'):
            raw_conn = db.connection().connection
            if hasattr(raw_conn, 'driver_connection'):
                raw_conn.driver_connection.prepare_threshold = None
    except Exception:
        pass

def get_ai_credits(db: Session, guild_id: str) -> int:
    disable_prepare(db)
    res = db.execute(text("SELECT ai_credits FROM server_configs WHERE guild_id = :gid"), {"gid": guild_id}).scalar()
    return res if res is not None else 0

def deduct_ai_credit(db: Session, guild_id: str):
    disable_prepare(db)
    db.execute(text("UPDATE server_configs SET ai_credits = ai_credits - 1 WHERE guild_id = :gid"), {"gid": guild_id})
    db.commit()

def save_ai_history(db: Session, guild_id: str, feature_type: str, input_data: dict, narrative: str):
    disable_prepare(db)
    db.execute(
        text("INSERT INTO ai_reports (guild_id, feature_type, input_data, result_narrative) VALUES (:gid, :ftype, :data, :narrative)"),
        {"gid": guild_id, "ftype": feature_type, "data": json.dumps(input_data), "narrative": narrative}
    )
    db.commit()
