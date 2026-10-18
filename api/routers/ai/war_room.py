from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.deps import get_active_server, get_db
from models import ClanMember
from api.services.web_ai import generate_narrative, get_base_prompt
from .utils import get_ai_credits, deduct_ai_credit, save_ai_history

router = APIRouter()

@router.get("/war-room")
def get_war_room(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # 1. Cari War terbaru
    war = db.execute(text("SELECT id, opponent_name, clan_stars, opp_stars, clan_destruction, opp_destruction, attacks_per_member, state FROM wars WHERE clan_tag = :ctag ORDER BY id DESC LIMIT 1"), {"ctag": server.clan_tag}).fetchone()
    
    if not war or war.state not in ['inWar', 'preparation']:
        return {"error": "Klan sedang tidak dalam state War."}
        
    war_id = war.id
    
    # 2. Tarik member kita (Normalisasi Tag: hapus '#' biar cocok)
    our_tags = {m.tag.replace('#', '').strip() for m in db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()}
    
    # 3. Tarik semua participant di war ini
    participants = db.execute(text("SELECT player_tag, player_name, townhall_level, attacks_used, attacks_allowed, map_position, best_opp_stars FROM war_participants WHERE war_id = :wid"), {"wid": war_id}).fetchall()
    
    # 4. Cek data attack (kalau war_attacks kosong, kita fallback ke best_opp_stars)
    has_attack_data = db.execute(text("SELECT COUNT(*) FROM war_attacks WHERE war_id = :wid"), {"wid": war_id}).scalar() > 0
    
    our_attackers = []
    enemy_targets = []
    
    for p in participants:
        p_tag_clean = p.player_tag.replace('#', '').strip()
        
        if p_tag_clean in our_tags:
            # Ini member kita
            if p.attacks_used < p.attacks_allowed:
                our_attackers.append({"name": p.player_name, "th": p.townhall_level, "attacks_left": p.attacks_allowed - p.attacks_used})
        else:
            # Ini musuh
            stars = 0
            if has_attack_data:
                # Kalau ada data di war_attacks, ambil bintang MAKSIMAL yang kita dapet di base musuh ini
                stars_res = db.execute(text("SELECT COALESCE(MAX(stars), 0) FROM war_attacks WHERE war_id = :wid AND defender_tag = :dtag"), {"wid": war_id, "dtag": p.player_tag}).scalar()
                stars = int(stars_res or 0)
            else:
                # Fallback kalau war_attacks kosong, pakai best_opp_stars (walaupun kadang gak akurat)
                stars = int(p.best_opp_stars or 0)
                
            if stars < 3:
                enemy_targets.append({"name": p.player_name, "th": p.townhall_level, "map_position": p.map_position, "stars": stars})

    # 5. Urutkan dari TH tertinggi
    our_attackers = sorted(our_attackers, key=lambda x: x['th'], reverse=True)
    enemy_targets = sorted(enemy_targets, key=lambda x: (x['th'], -x['map_position']), reverse=True)
    
    # 6. Matchmaking (Ambil maksimal 10)
    matchups = []
    for i in range(min(len(our_attackers), len(enemy_targets), 10)):
        matchups.append({"attacker": our_attackers[i], "target": enemy_targets[i]})

    return {
        "state": war.state, "opponent_name": war.opponent_name,
        "clan_stars": war.clan_stars, "opp_stars": war.opp_stars,
        "clan_destruction": float(war.clan_destruction or 0), "opp_destruction": float(war.opp_destruction or 0),
        "total_attacks_left": sum(a['attacks_left'] for a in our_attackers),
        "matchups": matchups, "credits": get_ai_credits(db, server.guild_id)
    }

@router.post("/war-room/enhance")
async def enhance_war_room(server = Depends(get_active_server), db: Session = Depends(get_db)):
    credits = get_ai_credits(db, server.guild_id)
    if credits <= 0: raise HTTPException(status_code=402, detail="Kredit AI Anda habis.")

    war_data = get_war_room(server, db)
    if "error" in war_data: raise HTTPException(status_code=400, detail=war_data["error"])

    matchup_text = "\n".join([f"- {m['attacker']['name']} (TH{m['attacker']['th']}) disarankan nyerang Base #{m['target']['map_position']} {m['target']['name']} (TH{m['target']['th']}, baru {m['target']['stars']} Star)" for m in war_data['matchups']])

    prompt = f"{get_base_prompt()}\nDATA WAR SAAT INI:\nKlan Kita: {war_data['clan_stars']} Bintang\nMusuh ({war_data['opponent_name']}): {war_data['opp_stars']} Bintang\nTotal Sisa Attack Kita: {war_data['total_attacks_left']}\n\nREKOMENDASI MATCHMAKING:\n{matchup_text}\n\nTuliskan ANALISIS STRATEGI WAR singkat (maksimal 3 poin) untuk Clan Leader. Fokus pada instruksi siapa harus nyerang siapa."
    
    result_text = await generate_narrative(prompt)
    deduct_ai_credit(db, server.guild_id)

    try:
        raw_data = {"clan_stars": war_data['clan_stars'], "opp_stars": war_data['opp_stars'], "total_attacks_left": war_data['total_attacks_left']}
        save_ai_history(db, server.guild_id, "war_room", raw_data, result_text.replace("<br>", "\n"))
    except Exception as e: print(f"Gagal simpan history: {e}")

    return {"narrative": result_text, "credits": get_ai_credits(db, server.guild_id)}
