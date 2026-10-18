import urllib.parse
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.deps import get_active_server, get_db
from api.services.web_ai import generate_narrative, get_base_prompt
from api.routers.clan import fetch_coc
from .utils import get_ai_credits, deduct_ai_credit, save_ai_history

router = APIRouter()

async def sync_opponents_if_needed(db: Session, clan_tag: str, war_id: int):
    last_sync = db.execute(text("SELECT MAX(created_at) FROM war_opponents WHERE war_id = :wid"), {"wid": war_id}).scalar()
    now = datetime.utcnow()
    if not last_sync or (now - last_sync.replace(tzinfo=None)) > timedelta(minutes=15):
        encoded_tag = urllib.parse.quote(clan_tag)
        live_war = await fetch_coc(f"/clans/{encoded_tag}/currentwar")
        if live_war and live_war.get("state") in ["inWar", "preparation"]:
            opp_members = live_war.get("opponent", {}).get("members", [])
            db.execute(text("DELETE FROM war_opponents WHERE war_id != :wid"), {"wid": war_id})
            for m in opp_members:
                best_stars = m.get("bestOpponentAttack", {}).get("stars", 0) if m.get("bestOpponentAttack") else 0
                exists = db.execute(text("SELECT id FROM war_opponents WHERE war_id = :wid AND player_tag = :tag"), {"wid": war_id, "tag": m.get("tag")}).scalar()
                if exists:
                    db.execute(text("UPDATE war_opponents SET best_stars = :stars WHERE id = :id"), {"stars": best_stars, "id": exists})
                else:
                    db.execute(text("INSERT INTO war_opponents (war_id, player_tag, player_name, townhall_level, map_position, best_stars) VALUES (:wid, :tag, :name, :th, :pos, :stars)"), {"wid": war_id, "tag": m.get("tag"), "name": m.get("name"), "th": m.get("townhallLevel"), "pos": m.get("mapPosition"), "stars": best_stars})
            db.commit()

@router.get("/war-room")
async def get_war_room(server = Depends(get_active_server), db: Session = Depends(get_db), filter_th: int = Query(None)):
    war = db.execute(text("SELECT id, state FROM wars WHERE clan_tag = :ctag ORDER BY id DESC LIMIT 1"), {"ctag": server.clan_tag}).fetchone()
    
    if not war:
        return {"error": "Belum ada data War di database."}
    if war.state == 'preparation':
        return {"error": "War masih dalam tahap Preparation."}
    if war.state in ['warEnded', 'notInWar']:
        return {"error": "War sudah selesai atau belum dimulai."}
        
    war_id = war.id
    await sync_opponents_if_needed(db, server.clan_tag, war_id)

    war_info = db.execute(text("SELECT opponent_name, clan_stars, opp_stars, clan_destruction, opp_destruction FROM wars WHERE id = :wid"), {"wid": war_id}).fetchone()
    
    our_participants = db.execute(text("SELECT player_name, townhall_level, attacks_used, attacks_allowed FROM war_participants WHERE war_id = :wid AND attacks_used < attacks_allowed"), {"wid": war_id}).fetchall()
    our_attackers = [{"name": p.player_name, "th": p.townhall_level, "attacks_left": p.attacks_allowed - p.attacks_used} for p in our_participants]
    our_attackers = sorted(our_attackers, key=lambda x: x['th'], reverse=True)

    # Filter TH (Opsional)
    query = "SELECT player_name, townhall_level, map_position, best_stars FROM war_opponents WHERE war_id = :wid AND best_stars < 3"
    params = {"wid": war_id}
    if filter_th:
        query += " AND townhall_level = :th"
        params["th"] = filter_th
        
    opp_targets = db.execute(text(query), params).fetchall()
    enemy_targets = [{"name": t.player_name, "th": t.townhall_level, "map_position": t.map_position, "stars": t.best_stars} for t in opp_targets]
    enemy_targets = sorted(enemy_targets, key=lambda x: x['th'], reverse=True)

    matchups = []
    for i in range(min(len(our_attackers), len(enemy_targets), 10)):
        matchups.append({"attacker": our_attackers[i], "target": enemy_targets[i]})

    return {
        "state": war.state, "opponent_name": war_info.opponent_name,
        "clan_stars": war_info.clan_stars, "opp_stars": war_info.opp_stars,
        "clan_destruction": float(war_info.clan_destruction or 0), "opp_destruction": float(war_info.opp_destruction or 0),
        "total_attacks_left": sum(a['attacks_left'] for a in our_attackers),
        "matchups": matchups, "credits": get_ai_credits(db, server.guild_id)
    }

@router.post("/war-room/enhance")
async def enhance_war_room(server = Depends(get_active_server), db: Session = Depends(get_db)):
    credits = get_ai_credits(db, server.guild_id)
    if credits <= 0: raise HTTPException(status_code=402, detail="Kredit AI Anda habis.")
    war_data = await get_war_room(server, db)
    if "error" in war_data: raise HTTPException(status_code=400, detail=war_data["error"])

    matchup_text = "\n".join([f"- {m['attacker']['name']} (TH{m['attacker']['th']}) disarankan nyerang Base #{m['target']['map_position']} {m['target']['name']} (TH{m['target']['th']}, baru {m['target']['stars']} Star)" for m in war_data['matchups']])
    prompt = f"{get_base_prompt()}\nDATA WAR:\nKita: {war_data['clan_stars']}★\nMusuh: {war_data['opp_stars']}★\nSisa Attack: {war_data['total_attacks_left']}\n\nMATCHMAKING:\n{matchup_text}\n\nTuliskan ANALISIS STRATEGI WAR (maks 3 poin) yang tegas dan to-the-point."
    
    result_text = await generate_narrative(prompt)
    deduct_ai_credit(db, server.guild_id)
    try:
        save_ai_history(db, server.guild_id, "war_room", {"clan_stars": war_data['clan_stars'], "opp_stars": war_data['opp_stars']}, result_text.replace("<br>", "\n"))
    except Exception as e: print(f"Gagal simpan history: {e}")
    return {"narrative": result_text, "credits": get_ai_credits(db, server.guild_id)}
