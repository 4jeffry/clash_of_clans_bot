import json
from sqlalchemy.orm import Session
from sqlalchemy import text

def get_ai_credits(db: Session, guild_id: str) -> int:
    res = db.execute(text("SELECT ai_credits FROM server_configs WHERE guild_id = :gid"), {"gid": guild_id}).scalar()
    return res if res is not None else 0

def deduct_ai_credit(db: Session, guild_id: str):
    db.execute(text("UPDATE server_configs SET ai_credits = ai_credits - 1 WHERE guild_id = :gid"), {"gid": guild_id})
    db.commit()

def save_ai_history(db: Session, guild_id: str, feature_type: str, input_data: dict, narrative: str):
    db.execute(
        text("INSERT INTO ai_reports (guild_id, feature_type, input_data, result_narrative) VALUES (:gid, :ftype, :data, :narrative)"),
        {"gid": guild_id, "ftype": feature_type, "data": json.dumps(input_data), "narrative": narrative}
    )
    db.commit()
