from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.deps import get_active_server, get_db
from api.services.web_ai import generate_narrative, get_base_prompt
from .utils import get_ai_credits, deduct_ai_credit, save_ai_history

router = APIRouter()

@router.get("/war-report")
def get_war_report(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # 1. Cari war terakhir yang udah selesai
    war = db.execute(text("SELECT id, opponent_name, clan_stars, opp_stars, clan_destruction, opp_destruction, result FROM wars WHERE clan_tag = :ctag AND state = 'warEnded' ORDER BY id DESC LIMIT 1"), {"ctag": server.clan_tag}).fetchone()
    
    if not war:
        return {"error": "Belum ada data War yang selesai."}

    war_id = war.id

    # 2. Cari MVP (Bintang Terbanyak)
    mvp_query = text("""
        SELECT attacker_name, SUM(stars) as total_stars, COUNT(*) as attacks
        FROM war_attacks 
        WHERE war_id = :wid 
        GROUP BY attacker_name 
        ORDER BY total_stars DESC, attacks ASC 
        LIMIT 1
    """)
    mvp_data = db.execute(mvp_query, {"wid": war_id}).fetchone()
    mvp = {"name": mvp_data.attacker_name, "stars": mvp_data.total_stars} if mvp_data else None

    # 3. Cari member yang tidak nyerang (0 attack)
    slackers_query = text("""
        SELECT player_name, townhall_level 
        FROM war_participants 
        WHERE war_id = :wid AND attacks_used = 0
    """)
    slackers = [{"name": s.player_name, "th": s.townhall_level} for s in db.execute(slackers_query, {"wid": war_id}).fetchall()]

    # 4. Hitung total attack terpakai
    total_attacks = db.execute(text("SELECT COUNT(*) FROM war_attacks WHERE war_id = :wid"), {"wid": war_id}).scalar()
    max_attacks = db.execute(text("SELECT SUM(attacks_allowed) FROM war_participants WHERE war_id = :wid"), {"wid": war_id}).scalar() or 1

    return {
        "war_result": war.result,
        "opponent_name": war.opponent_name,
        "clan_stars": war.clan_stars, "opp_stars": war.opp_stars,
        "clan_destruction": float(war.clan_destruction or 0), "opp_destruction": float(war.opp_destruction or 0),
        "mvp": mvp,
        "slackers": slackers,
        "attack_efficiency": round((total_attacks / max_attacks) * 100, 1),
        "credits": get_ai_credits(db, server.guild_id)
    }

@router.post("/war-report/enhance")
async def enhance_war_report(server = Depends(get_active_server), db: Session = Depends(get_db)):
    credits = get_ai_credits(db, server.guild_id)
    if credits <= 0: raise HTTPException(status_code=402, detail="Kredit AI habis.")

    report = get_war_report(server, db)
    if "error" in report: raise HTTPException(status_code=400, detail=report["error"])

    slacker_names = ", ".join([s['name'] for s in report['slackers']]) if report['slackers'] else "Tidak ada"
    mvp_name = report['mvp']['name'] if report['mvp'] else "Tidak ada"

    prompt = f"""
    {get_base_prompt()}
    DATA PASCA WAR:
    Hasil: {report['war_result']} vs {report['opponent_name']}
    Skor: {report['clan_stars']} - {report['opp_stars']}
    Efisiensi Attack: {report['attack_efficiency']}%
    MVP: {mvp_name}
    Member yang tidak nyerang (0 Attack): {slacker_names}

    Tuliskan EVALUASI PASCA WAR (maksimal 3 poin). Berikan pujian untuk MVP, teguran konstruktif untuk yang tidak nyerang, dan saran perbaikan taktik.
    """
    
    result_text = await generate_narrative(prompt)
    deduct_ai_credit(db, server.guild_id)

    try:
        save_ai_history(db, server.guild_id, "war_report", {"result": report['war_result'], "mvp": mvp_name}, result_text.replace("<br>", "\n"))
    except Exception as e: print(f"Gagal simpan history: {e}")

    return {"narrative": result_text, "credits": get_ai_credits(db, server.guild_id)}
