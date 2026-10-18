import urllib.parse
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.deps import get_active_server, get_db
from api.services.web_ai import generate_narrative, get_base_prompt
from api.routers.clan import fetch_coc
from .utils import get_ai_credits, deduct_ai_credit, save_ai_history

router = APIRouter()

@router.get("/war-room")
async def get_war_room(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # 1. Tarik data Live War dari Supercell API
    encoded_tag = urllib.parse.quote(server.clan_tag)
    live_war = await fetch_coc(f"/clans/{encoded_tag}/currentwar")
    
    if not live_war or live_war.get("state") in ["notInWar", "preparation"]:
        return {"error": "Klan sedang tidak dalam state War (atau masih preparation)."}

    clan = live_war.get("clan", {})
    opponent = live_war.get("opponent", {})
    
    clan_members = clan.get("members", [])
    opp_members = opponent.get("members", [])
    attacks_per_member = live_war.get("attacksPerMember", 2)

    # 2. Ambil Attacker Kita (Sisa Attack)
    our_attackers = []
    for m in clan_members:
        attacks_used = len(m.get("attacks", []))
        if attacks_used < attacks_per_member:
            our_attackers.append({
                "name": m.get("name"),
                "th": m.get("townhallLevel"),
                "attacks_left": attacks_per_member - attacks_used,
                "map_position": m.get("mapPosition")
            })
    
    # Urutkan Attacker dari TH tertinggi
    our_attackers = sorted(our_attackers, key=lambda x: x['th'], reverse=True)

    # 3. Ambil Target Musuh (Belum 3 Star)
    enemy_targets = []
    for m in opp_members:
        best_opp_stars = m.get("bestOpponentAttack", {}).get("stars", 0) if m.get("bestOpponentAttack") else 0
        if best_opp_stars < 3:
            enemy_targets.append({
                "name": m.get("name"),
                "th": m.get("townhallLevel"),
                "map_position": m.get("mapPosition"),
                "stars": best_opp_stars
            })
            
    # Urutkan Target dari TH tertinggi
    enemy_targets = sorted(enemy_targets, key=lambda x: x['th'], reverse=True)

    # 4. Matchmaking Logic (Greedy Match: Terkuat vs Terkuat)
    matchups = []
    for i in range(min(len(our_attackers), len(enemy_targets), 10)):
        matchups.append({"attacker": our_attackers[i], "target": enemy_targets[i]})

    total_attacks_left = sum(a['attacks_left'] for a in our_attackers)

    return {
        "state": live_war.get("state"),
        "opponent_name": opponent.get("name"),
        "clan_stars": clan.get("stars", 0),
        "opp_stars": opponent.get("stars", 0),
        "clan_destruction": clan.get("destructionPercentage", 0),
        "opp_destruction": opponent.get("destructionPercentage", 0),
        "total_attacks_left": total_attacks_left,
        "matchups": matchups,
        "credits": get_ai_credits(db, server.guild_id)
    }

@router.post("/war-room/enhance")
async def enhance_war_room(server = Depends(get_active_server), db: Session = Depends(get_db)):
    credits = get_ai_credits(db, server.guild_id)
    if credits <= 0: raise HTTPException(status_code=402, detail="Kredit AI Anda habis.")

    war_data = await get_war_room(server, db)
    if "error" in war_data: raise HTTPException(status_code=400, detail=war_data["error"])

    matchup_text = "\n".join([f"- {m['attacker']['name']} (TH{m['attacker']['th']}) disarankan nyerang Base #{m['target']['map_position']} {m['target']['name']} (TH{m['target']['th']}, baru {m['target']['stars']} Star)" for m in war_data['matchups']])

    prompt = f"{get_base_prompt()}\nDATA WAR SAAT INI:\nKlan Kita: {war_data['clan_stars']} Bintang\nMusuh ({war_data['opponent_name']}): {war_data['opp_stars']} Bintang\nTotal Sisa Attack Kita: {war_data['total_attacks_left']}\n\nREKOMENDASI MATCHMAKING:\n{matchup_text}\n\nTuliskan ANALISIS STRATEGI WAR singkat (maksimal 3 poin) untuk Clan Leader. Fokus pada instruksi siapa harus nyerang siapa berdasarkan sisa attack dan data di atas."
    
    result_text = await generate_narrative(prompt)
    deduct_ai_credit(db, server.guild_id)

    try:
        raw_data = {"clan_stars": war_data['clan_stars'], "opp_stars": war_data['opp_stars'], "total_attacks_left": war_data['total_attacks_left']}
        save_ai_history(db, server.guild_id, "war_room", raw_data, result_text.replace("<br>", "\n"))
    except Exception as e: print(f"Gagal simpan history: {e}")

    return {"narrative": result_text, "credits": get_ai_credits(db, server.guild_id)}
