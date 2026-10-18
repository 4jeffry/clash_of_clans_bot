from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, text
from api.deps import get_active_server, get_db
from models import War, ClanMember, WarHistory, CapitalRaid, CapitalParticipant, WarParticipant, WarAttack, WarParticipant
import os
import urllib.parse
import httpx

router = APIRouter()
COC_TOKEN = os.getenv('COC_API_TOKEN')

async def fetch_coc(endpoint: str):
    if not COC_TOKEN: return None
    url = f"https://cocproxy.royaleapi.dev/v1{endpoint}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers={"Authorization": f"Bearer {COC_TOKEN}"})
        return res.json() if res.status_code == 200 else None

# --- ENDPOINT BARU: LEADERBOARD ---
@router.get("/leaderboard")
def get_leaderboard(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Ambil top 10 donatur dari tabel members
    donors = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).order_by(desc(ClanMember.donations)).limit(10).all()
    return [{"name": m.name, "townhall": m.townhall_level, "score": m.donations, "type": "Donasi"} for m in donors]

# --- ENDPOINT BARU: RACE WAR ---
@router.get("/racewar")
def get_race_war(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Cari war aktif terakhir
    active_war = db.query(War).filter(War.clan_tag == server.clan_tag).order_by(desc(War.id)).first()
    if not active_war:
        return {"error": "Belum ada data War di database."}
    
    # Ambil partisipan war tersebut
    participants = db.query(WarParticipant).filter(WarParticipant.war_id == active_war.id).all()
    
    offense = []
    defense = []
    
    for p in participants:
        # Offense: Attack yang dipakai & bintang didapat
        offense.append({
            "name": p.player_name,
            "th": p.townhall_level,
            "atk_used": p.attacks_used,
            "atk_max": p.attacks_allowed,
            "stars": p.best_opp_stars, # Untuk sementara pakai ini, atau akumulasi dari WarAttack
            "destruction": float(p.best_opp_destruction or 0)
        })
        
        # Defense: Berapa kali diserang dan bintang yang diberikan ke lawan
        defense.append({
            "name": p.player_name,
            "th": p.townhall_level,
            "defended_count": p.opp_attacks_count,
            "stars_given": p.best_opp_stars,
            "destruction_given": float(p.best_opp_destruction or 0)
        })

    # Sortir
    offense.sort(key=lambda x: (x['stars'], x['destruction']), reverse=True)
    defense.sort(key=lambda x: (x['stars_given'], x['destruction_given']))

    return {"offense": offense, "defense": defense, "war_state": active_war.state}

# --- Endpoint DB Lama ---
@router.get("/capital")
def get_capital_info(server = Depends(get_active_server), db: Session = Depends(get_db)):
    raid = db.query(CapitalRaid).filter(CapitalRaid.clan_tag == server.clan_tag).order_by(desc(CapitalRaid.id)).first()
    if not raid: return {"error": "Belum ada data Raid."}
    return {"total_loot": raid.total_loot, "total_attacks": raid.total_attacks, "districts_destroyed": raid.districts_destroyed, "defensive_rewards": raid.defensive_rewards, "completed_raids": raid.raids_completed, "state": raid.state}

@router.get("/capitaldonations")
def get_capital_donations(server = Depends(get_active_server), db: Session = Depends(get_db)):
    latest = db.query(CapitalRaid).filter(CapitalRaid.clan_tag == server.clan_tag).order_by(desc(CapitalRaid.id)).first()
    if not latest: return []
    parts = db.query(CapitalParticipant).filter(CapitalParticipant.raid_id == latest.id).order_by(desc(CapitalParticipant.contributions)).limit(10).all()
    return [{"name": p.player_name, "townhall": p.townhall_level, "contributions": p.contributions} for p in parts]

@router.get("/raidstats")
async def get_raid_stats(server = Depends(get_active_server)):
    encoded_tag = urllib.parse.quote(server.clan_tag)
    clan_data = await fetch_coc(f"/clans/{encoded_tag}")
    raid_data = await fetch_coc(f"/clans/{encoded_tag}/capitalraidseasons")
    if not clan_data or "memberList" not in clan_data or not raid_data or "items" not in raid_data or not raid_data["items"]: return []
    all_members = {m['tag']: m['name'] for m in clan_data['memberList']}
    latest_raid = raid_data["items"][0]
    raid_members = {m['tag']: m for m in latest_raid.get("members", [])}
    result = []
    for tag, name in all_members.items():
        if tag not in raid_members:
            result.append({"name": name, "status": "Belum Attack", "attacks": 0, "max_attacks": 5, "loot": 0})
        else:
            rm = raid_members[tag]
            attacks, max_attacks, loot = rm.get("attacks", 0), rm.get("attackLimit", 5) + rm.get("bonusAttackLimit", 0), rm.get("capitalResourcesLooted", 0)
            status = "Belum Attack" if attacks == 0 else ("Sudah Attack" if attacks < max_attacks else "Max Attack")
            result.append({"name": name, "status": status, "attacks": attacks, "max_attacks": max_attacks, "loot": loot})
    result.sort(key=lambda x: ({"Belum Attack": 1, "Sudah Attack": 2, "Max Attack": 3}[x['status']], -x['loot']))
    return result

@router.get("/war")
def get_current_war(server = Depends(get_active_server), db: Session = Depends(get_db)):
    w = db.query(War).filter(War.clan_tag == server.clan_tag).order_by(desc(War.id)).first()
    if not w: return {"state": "notInWar", "clan_badge_url": server.clan_badge_url}
    return {"state": w.state, "clan_badge_url": server.clan_badge_url, "opponent_name": w.opponent_name, "opponent_tag": w.opponent_tag, "team_size": w.team_size, "clan_stars": w.clan_stars, "opp_stars": w.opp_stars, "clan_destruction": float(w.clan_destruction or 0), "opp_destruction": float(w.opp_destruction or 0), "start_time": w.start_time, "end_time": w.end_time, "result": w.result}

@router.get("/war/history")
def get_war_history(server = Depends(get_active_server), db: Session = Depends(get_db)):
    h = db.query(WarHistory).filter(WarHistory.clan_tag == server.clan_tag).order_by(desc(WarHistory.end_time)).limit(10).all()
    return [{"opponent_name": x.opponent_name, "result": x.result, "stars": x.stars, "destruction": float(x.destruction_percentage or 0), "end_time": x.end_time} for x in h]

@router.get("/members")
def get_members(server = Depends(get_active_server), db: Session = Depends(get_db)):
    m = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()
    return [{"tag": x.tag, "name": x.name, "role": x.role, "townhall_level": x.townhall_level, "donations": x.donations, "donations_received": x.donations_received, "last_updated": x.last_updated} for x in m]

@router.get("/donations")
def get_top_donations(server = Depends(get_active_server), db: Session = Depends(get_db)):
    m = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).order_by(desc(ClanMember.donations)).limit(5).all()
    return [{"tag": x.tag, "name": x.name, "role": x.role, "donations": x.donations, "donations_received": x.donations_received, "townhall_level": x.townhall_level} for x in m]

@router.get("/inactive")
def get_inactive(server = Depends(get_active_server), db: Session = Depends(get_db)):
    m = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).order_by(ClanMember.donations).limit(10).all()
    return [{"tag": x.tag, "name": x.name, "role": x.role, "donations": x.donations, "last_updated": x.last_updated, "townhall_level": x.townhall_level} for x in m]

@router.get("/cwl")
def get_cwl(server = Depends(get_active_server), db: Session = Depends(get_db)):
    w = db.query(War).filter(War.clan_tag == server.clan_tag, War.is_cwl == True).order_by(desc(War.start_time)).limit(10).all()
    return [{"id": x.id, "opponent_name": x.opponent_name, "opponent_tag": x.opponent_tag, "state": x.state, "result": x.result, "clan_stars": x.clan_stars, "clan_destruction": float(x.clan_destruction or 0), "opp_stars": x.opp_stars, "opp_destruction": float(x.opp_destruction or 0), "start_time": x.start_time, "end_time": x.end_time} for x in w]

@router.get("/member/{player_tag}")
def get_member_detail(player_tag: str, server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Format tag (ganti # jadi %23)
    formatted_tag = urllib.parse.quote(player_tag)
    
    # 1. Ambil dari DB lokal (ClanMember)
    member = db.query(ClanMember).filter(
        ClanMember.clan_tag == server.clan_tag,
        ClanMember.tag == formatted_tag
    ).first()
    
    if not member:
        # Coba cari tanpa %23 kalau format dari frontend beda
        member = db.query(ClanMember).filter(
            ClanMember.clan_tag == server.clan_tag,
            ClanMember.tag == player_tag
        ).first()
        
    if not member:
        return {"error": "Member tidak ditemukan di database."}
        
    # 2. Hitung stats War terakhir (dari WarParticipant)
    # Ambil war ID terakhir
    last_war = db.query(War).filter(War.clan_tag == server.clan_tag).order_by(desc(War.id)).first()
    
    war_stats = {"stars": 0, "destruction": 0, "attacks_used": 0, "attacks_allowed": 2}
    if last_war:
        wp = db.query(WarParticipant).filter(
            WarParticipant.war_id == last_war.id,
            WarParticipant.player_tag == member.tag
        ).first()
        if wp:
            # Total stars dari WarAttack (jika ada) atau dari best_opp_stars
            # Kita pakai akumulasi dari WarAttack untuk akurasi
            attacks = db.query(WarAttack).filter(
                WarAttack.war_id == last_war.id,
                WarAttack.attacker_tag == member.tag
            ).all()
            
            total_stars = sum(a.stars for a in attacks) if attacks else 0
            total_dest = sum(a.destruction_percentage for a in attacks) if attacks else 0
            # Rata-rata destruction per attack
            avg_dest = total_dest / len(attacks) if attacks else 0
            
            war_stats = {
                "stars": total_stars,
                "destruction": round(avg_dest, 1),
                "attacks_used": len(attacks),
                "attacks_allowed": wp.attacks_allowed
            }

    return {
        "tag": member.tag,
        "name": member.name,
        "role": member.role,
        "townhall_level": member.townhall_level,
        "donations": member.donations,
        "donations_received": member.donations_received,
        "war_stats": war_stats
    }

@router.get("/compare")
def compare_members(tag1: str, tag2: str, server = Depends(get_active_server), db: Session = Depends(get_db)):
    formatted_tag1 = urllib.parse.quote(tag1)
    formatted_tag2 = urllib.parse.quote(tag2)
    
    def get_stats(player_tag):
        member = db.query(ClanMember).filter(
            ClanMember.clan_tag == server.clan_tag,
            ClanMember.tag == player_tag
        ).first()
        if not member:
            return None
            
        last_war = db.query(War).filter(War.clan_tag == server.clan_tag).order_by(desc(War.id)).first()
        war_stats = {"stars": 0, "destruction": 0, "attacks_used": 0, "attacks_allowed": 2}
        
        if last_war:
            wp = db.query(WarParticipant).filter(
                WarParticipant.war_id == last_war.id,
                WarParticipant.player_tag == member.tag
            ).first()
            if wp:
                attacks = db.query(WarAttack).filter(
                    WarAttack.war_id == last_war.id,
                    WarAttack.attacker_tag == member.tag
                ).all()
                total_stars = sum(a.stars for a in attacks) if attacks else 0
                total_dest = sum(a.destruction_percentage for a in attacks) if attacks else 0
                avg_dest = total_dest / len(attacks) if attacks else 0
                
                war_stats = {
                    "stars": total_stars,
                    "destruction": round(avg_dest, 1),
                    "attacks_used": len(attacks),
                    "attacks_allowed": wp.attacks_allowed
                }

        return {
            "tag": member.tag,
            "name": member.name,
            "townhall_level": member.townhall_level,
            "donations": member.donations,
            "donations_received": member.donations_received,
            "war_stats": war_stats
        }

    return {
        "player1": get_stats(formatted_tag1) or get_stats(tag1),
        "player2": get_stats(formatted_tag2) or get_stats(tag2)
    }

@router.get("/recap-war")
def get_recap_war(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Ambil war terakhir (bisa war aktif atau yang udah selesai)
    last_war = db.query(War).filter(War.clan_tag == server.clan_tag).order_by(desc(War.id)).first()
    if not last_war:
        return {"error": "Belum ada data War di database."}

    participants = db.query(WarParticipant).filter(WarParticipant.war_id == last_war.id).all()
    
    result = []
    for p in participants:
        # Ambil semua attack dari player ini di war ini
        attacks = db.query(WarAttack).filter(
            WarAttack.war_id == last_war.id,
            WarAttack.attacker_tag == p.player_tag
        ).order_by(WarAttack.order_num).all()

        # Hitung total
        total_stars = sum(a.stars for a in attacks) if attacks else 0
        total_dest = sum(a.destruction_percentage for a in attacks) if attacks else 0

        result.append({
            "name": p.player_name,
            "th": p.townhall_level,
            "map_pos": p.map_position,
            "attacks_used": len(attacks),
            "attacks_allowed": p.attacks_allowed,
            "total_stars": total_stars,
            "total_destruction": total_dest,
            "war_state": last_war.state,
            "opponent": last_war.opponent_name
        })

    # Urutkan berdasarkan total bintang tertinggi
    # Sortir berdasarkan TH tertinggi dulu, kalau sama baru lihat Map Position
    result.sort(key=lambda x: (-x['th'], x['map_pos']))
    
    return {
        "opponent": last_war.opponent_name,
        "state": last_war.state,
        "data": result
    }

@router.get("/recap-cwl")
def get_recap_cwl(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Ambil season CWL terakhir
    season = db.query(CWLSeason).filter(CWLSeason.clan_tag == server.clan_tag).order_by(desc(CWLSeason.id)).first()
    if not season:
        return {"error": "Belum ada data season CWL di database."}

    # Ambil semua war di season ini
    wars = db.query(War).filter(War.cwl_season_id == season.id).all()
    if not wars:
        return {"error": "Tidak ada data perang di season CWL terakhir."}

    war_ids = [w.id for w in wars]
    
    # Ambil semua partisipan di semua war tersebut
    participants = db.query(WarParticipant).filter(WarParticipant.war_id.in_(war_ids)).all()

    stats = {}
    for p in participants:
        if p.player_tag not in stats:
            stats[p.player_tag] = {
                "name": p.player_name,
                "th": p.townhall_level,
                "total_stars": 0,
                "total_dest": 0.0,
                "attacks_used": 0
            }
        
        # Ambil attack dari player ini di war tertentu
        attacks = db.query(WarAttack).filter(
            WarAttack.war_id == p.war_id,
            WarAttack.attacker_tag == p.player_tag
        ).all()
        
        stars = sum(a.stars for a in attacks) if attacks else 0
        dest = sum(a.destruction_percentage for a in attacks) if attacks else 0
        
        stats[p.player_tag]["total_stars"] += stars
        stats[p.player_tag]["total_dest"] += dest
        stats[p.player_tag]["attacks_used"] += len(attacks)

    result = list(stats.values())
    
    # Hitung rata-rata destruction per attack
    for r in result:
        if r["attacks_used"] > 0:
            r["avg_dest"] = round(r["total_dest"] / r["attacks_used"], 1)
        else:
            r["avg_dest"] = 0.0

    # Sortir berdasarkan TH tertinggi, lalu bintang terbanyak
    result.sort(key=lambda x: (-x['th'], -x['total_stars']))
    
    return {
        "season": season.month,
        "data": result
    }

# --- ENDPOINT TH COMPOSITION ---
@router.get("/th-composition")
def get_th_composition(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Ambil war terakhir
    last_war = db.query(War).filter(War.clan_tag == server.clan_tag).order_by(desc(War.id)).first()
    if not last_war:
        return {"error": "Belum ada data War."}
    
    participants = db.query(WarParticipant).filter(WarParticipant.war_id == last_war.id).all()
    if not participants:
        return {"error": "Tidak ada partisipan di war terakhir."}
        
    # Hitung jumlah per TH
    comp = {}
    for p in participants:
        th = p.townhall_level or 0
        if th not in comp:
            comp[th] = 0
        comp[th] += 1
        
    # Format jadi array dan urutkan dari TH tertinggi
    result = [{"th": k, "count": v} for k, v in comp.items() if k > 0]
    result.sort(key=lambda x: x["th"], reverse=True)
    
    return {
        "opponent": last_war.opponent_name,
        "data": result
    }

# --- ENDPOINT RACE CWL ---
@router.get("/racecwl")
def get_race_cwl(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Ambil war CWL terakhir yang lagi jalan
    active_war = db.query(War).filter(War.clan_tag == server.clan_tag, War.is_cwl == True).order_by(desc(War.id)).first()
    if not active_war:
        return {"error": "Belum ada data CWL di database."}
    
    participants = db.query(WarParticipant).filter(WarParticipant.war_id == active_war.id).all()
    
    offense = []
    defense = []
    for p in participants:
        attacks = db.query(WarAttack).filter(WarAttack.war_id == active_war.id, WarAttack.attacker_tag == p.player_tag).all()
        total_stars = sum(a.stars for a in attacks) if attacks else 0
        total_dest = sum(a.destruction_percentage for a in attacks) if attacks else 0
        
        offense.append({
            "name": p.player_name,
            "th": p.townhall_level,
            "atk_used": len(attacks),
            "atk_max": p.attacks_allowed,
            "stars": total_stars,
            "destruction": total_dest
        })
        
        defense.append({
            "name": p.player_name,
            "th": p.townhall_level,
            "defended_count": p.opp_attacks_count,
            "stars_given": p.best_opp_stars,
            "destruction_given": float(p.best_opp_destruction or 0)
        })

    offense.sort(key=lambda x: (x['stars'], x['destruction']), reverse=True)
    defense.sort(key=lambda x: (x['stars_given'], x['destruction_given']))

    return {"offense": offense, "defense": defense, "war_state": active_war.state}

# --- REWARD MANAGEMENT ---
from pydantic import BaseModel
from models import RaceReward
import datetime


class RewardUpdatePayload(BaseModel):
    reward_note: str

class RewardPayload(BaseModel):
    player_tag: str
    reward_note: str

@router.get("/rewards")
def get_rewards(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # 1. Ambil semua member di clan ini
    members_data = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()
    members = {m.tag: m.name for m in members_data}
    member_tags = list(members.keys())
    
    if not member_tags:
        return []

    # 2. Ambil reward berdasarkan player_tag yang ada di clan ini (gak peduli scope_type-nya apa)
    rewards = db.query(RaceReward).filter(
        RaceReward.player_tag.in_(member_tags)
    ).order_by(desc(RaceReward.claimed_at)).limit(50).all()
    
    result = []
    for r in rewards:
        name = members.get(r.player_tag, "Unknown")
        result.append({
            "id": r.id,
            "player_tag": r.player_tag,
            "name": name,
            "note": r.reward_note,
            "scope": r.scope_type,
            "date": r.claimed_at
        })
    return result

@router.post("/rewards")
def give_reward(payload: RewardPayload, server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Validasi member ada di klan
    member = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag, ClanMember.tag == payload.player_tag).first()
    if not member:
        return {"error": "Member tidak ditemukan di clan ini."}
        
    new_reward = RaceReward(
        scope_type='clan',
        scope_id=0, # Dummy ID karena kita filter by clan_tag lewat member tag
        player_tag=payload.player_tag,
        reward_note=payload.reward_note,
        claimed_at=datetime.datetime.utcnow()
    )
    db.add(new_reward)
    db.commit()
    return {"success": True, "message": "Reward berhasil dicatat."}


@router.delete("/rewards/{reward_id}")
def delete_reward(reward_id: int, db: Session = Depends(get_db)):
    reward = db.query(RaceReward).filter(RaceReward.id == reward_id).first()
    if not reward:
        raise HTTPException(status_code=404, detail="Reward tidak ditemukan")
    db.delete(reward)
    db.commit()
    return {"success": True, "message": "Reward berhasil dihapus"}

@router.put("/rewards/{reward_id}")
def update_reward(reward_id: int, payload: RewardUpdatePayload, db: Session = Depends(get_db)):
    reward = db.query(RaceReward).filter(RaceReward.id == reward_id).first()
    if not reward:
        raise HTTPException(status_code=404, detail="Reward tidak ditemukan")
    reward.reward_note = payload.reward_note
    db.commit()
    return {"success": True, "message": "Reward berhasil diupdate"}


@router.get("/dashboard")
def get_dashboard_data(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # 1. Tren Donasi (7 hari terakhir)
    donation_trend = db.execute(
        text("""
            SELECT snap_date, SUM(donations) as total_donations 
            FROM member_snapshots 
            WHERE clan_tag = :ctag 
            GROUP BY snap_date 
            ORDER BY snap_date ASC 
            LIMIT 7
        """), {"ctag": server.clan_tag}
    ).fetchall()
    
    # 2. Win Rate War
    war_results = db.execute(
        text("SELECT result, COUNT(*) as count FROM war_history WHERE clan_tag = :ctag GROUP BY result"), 
        {"ctag": server.clan_tag}
    ).fetchall()
    
    # 3. Top 5 Donatur
    top_donors = db.execute(
        text("SELECT name, donations FROM members WHERE clan_tag = :ctag ORDER BY donations DESC LIMIT 5"), 
        {"ctag": server.clan_tag}
    ).fetchall()

    # Format Data
    trend_labels = [row.snap_date.strftime('%d %b') if row.snap_date else '-' for row in donation_trend]
    trend_data = [int(row.total_donations or 0) for row in donation_trend]
    
    win = 0
    lose = 0
    for r in war_results:
        if r.result == 'win': win = r.count
        elif r.result == 'lose': lose = r.count

    return {
        "donation_trend": {"labels": trend_labels, "data": trend_data},
        "war_stats": {"win": win, "lose": lose},
        "top_donors": {
            "labels": [row.name for row in top_donors],
            "data": [int(row.donations or 0) for row in top_donors]
        }
    }
