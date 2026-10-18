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
    war = db.execute(text("SELECT id, opponent_name, clan_stars, opp_stars, clan_destruction, opp_destruction, team_size, state FROM wars WHERE clan_tag = :ctag ORDER BY id DESC LIMIT 1"), {"ctag": server.clan_tag}).fetchone()
    
    if not war or war.state not in ['inWar', 'preparation']:
        return {"error": "Klan sedang tidak dalam state War."}
        
    war_id = war.id
    team_size = war.team_size or 15
    
    # 2. Tarik data member kita yang masih punya sisa attack
    our_participants = db.execute(text("SELECT player_name, townhall_level, attacks_used, attacks_allowed FROM war_participants WHERE war_id = :wid AND attacks_used < attacks_allowed"), {"wid": war_id}).fetchall()
    
    our_attackers = [{"name": p.player_name, "th": p.townhall_level, "attacks_left": p.attacks_allowed - p.attacks_used} for p in our_participants]
    our_attackers = sorted(our_attackers, key=lambda x: x['th'], reverse=True)
    
    total_attacks_left = sum(a['attacks_left'] for a in our_attackers)

    # 3. Cari Base Musuh yang belum 3 star dari tabel war_attacks
    # (Karena kita gak punya data nama musuh, kita pake nomor base / map position)
    attacks_data = db.execute(text("SELECT defender_map_position, MAX(stars) as max_stars FROM war_attacks WHERE war_id = :wid GROUP BY defender_map_position"), {"wid": war_id}).fetchall()
    
    attacked_positions = {row.defender_map_position: row.max_stars for row in attacks_data}
    
    # Base 1 sampai 15, cari yang belum 3 star
    enemy_targets = []
    for pos in range(1, team_size + 1):
        stars = attacked_positions.get(pos, 0)
        if stars < 3:
            enemy_targets.append({"map_position": pos, "stars": stars})
            
    # Urutkan target dari base nomor terkecil (asumsi base 1-5 paling kuat, kita urutkan dari atas ke bawah)
    # Kalau mau dari bawah (paling lemah), tinggal di-reverse
    enemy_targets = sorted(enemy_targets, key=lambda x: x['map_position'])

    # 4. Matchmaking (Top 10)
    matchups = []
    for i in range(min(len(our_attackers), len(enemy_targets), 10)):
        matchups.append({"attacker": our_attackers[i], "target": enemy_targets[i]})

    return {
        "state": war.state, "opponent_name": war.opponent_name,
        "clan_stars": war.clan_stars, "opp_stars": war.opp_stars,
        "clan_destruction": float(war.clan_destruction or 0), "opp_destruction": float(war.opp_destruction or 0),
        "total_attacks_left": total_attacks_left,
        "matchups": matchups, "credits": get_ai_credits(db, server.guild_id)
    }

@router.post("/war-room/enhance")
async def enhance_war_room(server = Depends(get_active_server), db: Session = Depends(get_db)):
    credits = get_ai_credits(db, server.guild_id)
    if credits <= 0: raise HTTPException(status_code=402, detail="Kredit AI Anda habis.")

    war_data = get_war_room(server, db)
    if "error" in war_data: raise HTTPException(status_code=400, detail=war_data["error"])

    matchup_text = "\n".join([f"- {m['attacker']['name']} (TH{m['attacker']['th']}) disarankan nyerang Base #{m['target']['map_position']} (Baru {m['target']['stars']} Star)" for m in war_data['matchups']])

    prompt = f"{get_base_prompt()}\nDATA WAR SAAT INI:\nKlan Kita: {war_data['clan_stars']} Bintang\nMusuh ({war_data['opponent_name']}): {war_data['opp_stars']} Bintang\nTotal Sisa Attack Kita: {war_data['total_attacks_left']}\n\nREKOMENDASI MATCHMAKING (Berdasarkan Base Musuh yang belum 3 Star):\n{matchup_text}\n\nTuliskan ANALISIS STRATEGI WAR singkat (maksimal 3 poin) untuk Clan Leader. Fokus pada instruksi siapa harus nyerang Base nomor berapa."
    
    result_text = await generate_narrative(prompt)
    deduct_ai_credit(db, server.guild_id)

    try:
        raw_data = {"clan_stars": war_data['clan_stars'], "opp_stars": war_data['opp_stars'], "total_attacks_left": war_data['total_attacks_left']}
        save_ai_history(db, server.guild_id, "war_room", raw_data, result_text.replace("<br>", "\n"))
    except Exception as e: print(f"Gagal simpan history: {e}")

    return {"narrative": result_text, "credits": get_ai_credits(db, server.guild_id)}
