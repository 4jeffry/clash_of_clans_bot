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
        return {"error": "Belum ada data Raid Weekend di database."}
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
