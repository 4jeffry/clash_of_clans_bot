from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from api.deps import get_active_server, get_db
from models import War, ClanMember, WarHistory, CapitalRaid, CapitalParticipant

router = APIRouter()

@router.get("/capital")
def get_capital_info(server = Depends(get_active_server), db: Session = Depends(get_db)):
    raid = db.query(CapitalRaid).filter(CapitalRaid.clan_tag == server.clan_tag).order_by(desc(CapitalRaid.id)).first()
    if not raid:
        return {"error": "Belum ada data Raid Weekend di database. Tunggu bot sinkronisasi."}
    return {
        "total_loot": raid.total_loot,
        "total_attacks": raid.total_attacks,
        "districts_destroyed": raid.districts_destroyed,
        "defensive_rewards": raid.defensive_rewards,
        "completed_raids": raid.raids_completed,
        "state": raid.state
    }

@router.get("/capitaldonations")
def get_capital_donations(server = Depends(get_active_server), db: Session = Depends(get_db)):
    latest_raid = db.query(CapitalRaid).filter(CapitalRaid.clan_tag == server.clan_tag).order_by(desc(CapitalRaid.id)).first()
    if not latest_raid:
        return []
    
    participants = db.query(CapitalParticipant).filter(CapitalParticipant.raid_id == latest_raid.id).order_by(desc(CapitalParticipant.contributions)).limit(10).all()
    return [{"name": p.player_name, "townhall": p.townhall_level, "contributions": p.contributions} for p in participants]

# --- Endpoint lama tetap ada ---
@router.get("/war")
def get_current_war(server = Depends(get_active_server), db: Session = Depends(get_db)):
    current_war = db.query(War).filter(War.clan_tag == server.clan_tag).order_by(desc(War.id)).first()
    if not current_war:
        return {"state": "notInWar", "message": "Belum ada data war di database.", "clan_badge_url": server.clan_badge_url}
    return {
        "state": current_war.state, "clan_badge_url": server.clan_badge_url, "opponent_name": current_war.opponent_name,
        "opponent_tag": current_war.opponent_tag, "team_size": current_war.team_size, "clan_stars": current_war.clan_stars,
        "opp_stars": current_war.opp_stars, "clan_destruction": float(current_war.clan_destruction or 0),
        "opp_destruction": float(current_war.opp_destruction or 0), "start_time": current_war.start_time,
        "end_time": current_war.end_time, "result": current_war.result
    }

@router.get("/war/history")
def get_war_history(server = Depends(get_active_server), db: Session = Depends(get_db)):
    history = db.query(WarHistory).filter(WarHistory.clan_tag == server.clan_tag).order_by(desc(WarHistory.end_time)).limit(10).all()
    return [{"opponent_name": h.opponent_name, "result": h.result, "stars": h.stars, "destruction": float(h.destruction_percentage or 0), "end_time": h.end_time} for h in history]

@router.get("/members")
def get_members(server = Depends(get_active_server), db: Session = Depends(get_db)):
    members = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()
    return [{"tag": m.tag, "name": m.name, "role": m.role, "townhall_level": m.townhall_level, "donations": m.donations, "donations_received": m.donations_received, "last_updated": m.last_updated} for m in members]

@router.get("/donations")
def get_top_donations(server = Depends(get_active_server), db: Session = Depends(get_db)):
    top_donors = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).order_by(desc(ClanMember.donations)).limit(5).all()
    return [{"tag": m.tag, "name": m.name, "role": m.role, "donations": m.donations, "donations_received": m.donations_received, "townhall_level": m.townhall_level} for m in top_donors]

@router.get("/inactive")
def get_inactive_members(server = Depends(get_active_server), db: Session = Depends(get_db)):
    inactive = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).order_by(ClanMember.donations).limit(10).all()
    return [{"tag": m.tag, "name": m.name, "role": m.role, "donations": m.donations, "last_updated": m.last_updated, "townhall_level": m.townhall_level} for m in inactive]

@router.get("/cwl")
def get_cwl_history(server = Depends(get_active_server), db: Session = Depends(get_db)):
    cwl_wars = db.query(War).filter(War.clan_tag == server.clan_tag, War.is_cwl == True).order_by(desc(War.start_time)).limit(10).all()
    return [{"id": w.id, "opponent_name": w.opponent_name, "opponent_tag": w.opponent_tag, "state": w.state, "result": w.result, "clan_stars": w.clan_stars, "clan_destruction": float(w.clan_destruction or 0), "opp_stars": w.opp_stars, "opp_destruction": float(w.opp_destruction or 0), "start_time": w.start_time, "end_time": w.end_time} for w in cwl_wars]
