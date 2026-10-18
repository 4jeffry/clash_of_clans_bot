import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.deps import get_active_server, get_db
from models import ServerConfig, ClanMember
from api.services.web_ai import generate_narrative, get_base_prompt
from collections import Counter

router = APIRouter()

# --- HELPER CREDITS ---
def get_ai_credits(db: Session, guild_id: str) -> int:
    res = db.execute(text("SELECT ai_credits FROM server_configs WHERE guild_id = :gid"), {"gid": guild_id}).scalar()
    return res if res is not None else 0

def deduct_ai_credit(db: Session, guild_id: str):
    db.execute(text("UPDATE server_configs SET ai_credits = ai_credits - 1 WHERE guild_id = :gid"), {"gid": guild_id})
    db.commit()

# --- HELPER HISTORY ---
def save_ai_history(db: Session, guild_id: str, feature_type: str, input_data: dict, narrative: str):
    db.execute(
        text("INSERT INTO ai_reports (guild_id, feature_type, input_data, result_narrative) VALUES (:gid, :ftype, :data, :narrative)"),
        {
            "gid": guild_id,
            "ftype": feature_type,
            "data": json.dumps(input_data),
            "narrative": narrative
        }
    )
    db.commit()

# --- ENDPOINT 1: RULE-BASED ---
@router.get("/audit")
def get_audit_rule_based(server = Depends(get_active_server), db: Session = Depends(get_db)):
    members = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()
    if not members:
        return {"error": "Belum ada data member."}

    total_members = len(members)
    total_donations = sum(m.donations for m in members)
    avg_donations = total_donations // total_members if total_members > 0 else 0
    zero_donors = [m.name for m in members if m.donations == 0]
    top_donors = [{"name": m.name, "score": m.donations} for m in sorted(members, key=lambda x: x.donations, reverse=True)[:5]]
    th_levels = Counter([m.townhall_level for m in members if m.townhall_level])
    th_summary = [{"th": th, "count": count} for th, count in sorted(th_levels.items(), reverse=True)]

    health_pct = min(100, int((avg_donations / 500) * 100)) if avg_donations > 0 else 0
    
    narrative = f"STATUS UTAMA:\n- Kesehatan klan diperkirakan {health_pct}% berdasarkan rata-rata donasi.\n\n"
    narrative += f"EVALUASI MEMBER:\n- Total {total_members} member dengan rata-rata donasi {avg_donations}.\n"
    narrative += f"- Ditemukan {len(zero_donors)} member pasif (donasi 0).\n\n"
    narrative += f"ACTION PLAN:\n- Berikan apresiasi ke Top Donatur ({top_donors[0]['name'] if top_donors else 'N/A'}).\n- Evaluasi member pasif untuk rotasi war."

    raw_data = {
        "total_members": total_members,
        "active_members": total_members - len(zero_donors),
        "zero_donors_count": len(zero_donors),
        "avg_donations": avg_donations,
        "top_donors": top_donors,
        "th_summary": th_summary
    }

    return {
        "raw_data": raw_data,
        "narrative": narrative,
        "credits": get_ai_credits(db, server.guild_id)
    }

# --- ENDPOINT 2: ENHANCE WITH AI ---
@router.post("/audit/enhance")
async def enhance_audit(server = Depends(get_active_server), db: Session = Depends(get_db)):
    credits = get_ai_credits(db, server.guild_id)
    if credits <= 0:
        raise HTTPException(status_code=402, detail="Kredit AI Anda habis. Silakan top up.")

    members = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()
    if not members:
        raise HTTPException(status_code=404, detail="Belum ada data member untuk dianalisis.")

    total_members = len(members)
    avg_donations = sum(m.donations for m in members) // total_members if total_members > 0 else 0
    zero_donors = [m.name for m in members if m.donations == 0][:10]
    top_donors = [f"{m.name} ({m.donations})" for m in sorted(members, key=lambda x: x.donations, reverse=True)[:5]]
    th_levels = Counter([m.townhall_level for m in members if m.townhall_level])
    th_summary = ", ".join([f"TH{th}: {count}" for th, count in sorted(th_levels.items(), reverse=True)])

    prompt = f"""
    {get_base_prompt()}
    DATA KLAN:
    Member: {total_members}/50
    TH: {th_summary}
    Rata-rata Donasi: {avg_donations}
    Top Donatur: {', '.join(top_donors)}
    Pasif: {', '.join(zero_donors)}

    FORMAT OUTPUT:
    AUDIT KESEHATAN KLAN

    1. STATUS UTAMA
    [1 kalimat skor kesehatan]

    2. EVALUASI MEMBER
    [1 kalimat evaluasi]

    3. ACTION PLAN
    [2 poin instruksi singkat]
    """
    
    result_text = await generate_narrative(prompt)
    deduct_ai_credit(db, server.guild_id)

    # Simpan ke History (Raw SQL)
    try:
        # Ambil raw data lagi buat disimpen
        raw_data = {
            "total_members": total_members,
            "zero_donors_count": len(zero_donors),
            "avg_donations": avg_donations
        }
        save_ai_history(db, server.guild_id, "audit_enhance", raw_data, result_text.replace("<br>", "\n"))
    except Exception as e:
        print(f"Gagal simpan history: {e}") # Biar ga crash kalau tabel belum dibikin

    return {
        "narrative": result_text,
        "credits": get_ai_credits(db, server.guild_id)
    }

# --- ENDPOINT 3: GET HISTORY ---
@router.get("/history")
def get_ai_history(server = Depends(get_active_server), db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT id, feature_type, created_at, result_narrative FROM ai_reports WHERE guild_id = :gid ORDER BY created_at DESC LIMIT 20"),
        {"gid": server.guild_id}
    ).fetchall()
    
    return [
        {
            "id": str(r[0]),
            "type": r[1],
            "date": r[2],
            "snippet": r[3][:100] + "..." if len(r[3]) > 100 else r[3]
        } for r in rows
    ]


@router.get("/history/{report_id}")
def get_ai_history_detail(report_id: str, server = Depends(get_active_server), db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT id, feature_type, input_data, result_narrative, created_at FROM ai_reports WHERE id = :rid AND guild_id = :gid"),
        {"rid": report_id, "gid": server.guild_id}
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Report tidak ditemukan")
        
    return {
        "id": str(row[0]),
        "type": row[1],
        "raw_data": row[2],
        "narrative": row[3],
        "date": row[4]
    }
