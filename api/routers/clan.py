from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from api.deps import get_active_server, get_db
from models import War, ClanMember, WarHistory

router = APIRouter()

@router.get("/war")
def get_current_war(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Ambil data war terbaru dari DB
    current_war = db.query(War).filter(War.clan_tag == server.clan_tag).order_by(desc(War.id)).first()
    if not current_war:
        return {"state": "notInWar", "message": "Belum ada data war di database.", "clan_badge_url": server.clan_badge_url}
    
    return {
        "state": current_war.state,
        "clan_badge_url": server.clan_badge_url,
        "clan_badge_url": server.clan_badge_url,
        "opponent_name": current_war.opponent_name,
        "opponent_tag": current_war.opponent_tag,
        "team_size": current_war.team_size,
        "clan_stars": current_war.clan_stars,
        "opp_stars": current_war.opp_stars,
        "clan_destruction": float(current_war.clan_destruction or 0),
        "opp_destruction": float(current_war.opp_destruction or 0),
        "start_time": current_war.start_time,
        "end_time": current_war.end_time,
        "result": current_war.result
    }

@router.get("/war/history")
def get_war_history(server = Depends(get_active_server), db: Session = Depends(get_db)):
    history = db.query(WarHistory).filter(WarHistory.clan_tag == server.clan_tag).order_by(desc(WarHistory.end_time)).limit(10).all()
    return [
        {
            "opponent_name": h.opponent_name,
            "result": h.result,
            "stars": h.stars,
            "destruction": float(h.destruction_percentage or 0),
            "end_time": h.end_time
        } for h in history
    ]

@router.get("/members")
def get_members(server = Depends(get_active_server), db: Session = Depends(get_db)):
    members = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()
    if not members:
        return []
    
    return [
        {
            "tag": m.tag,
            "name": m.name,
            "role": m.role,
            "townhall_level": m.townhall_level,
            "donations": m.donations,
            "donations_received": m.donations_received,
            "last_updated": m.last_updated
        } for m in members
    ]

@router.get("/cwl")
def get_cwl_history(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Ambil data war yang is_cwl = True
    cwl_wars = db.query(War).filter(
        War.clan_tag == server.clan_tag, 
        War.is_cwl == True
    ).order_by(desc(War.start_time)).limit(10).all()
    
    if not cwl_wars:
        return []
        
    return [
        {
            "id": w.id,
            "opponent_name": w.opponent_name,
            "opponent_tag": w.opponent_tag,
            "state": w.state,
            "result": w.result,
            "clan_stars": w.clan_stars,
            "clan_destruction": float(w.clan_destruction or 0),
            "opp_stars": w.opp_stars,
            "opp_destruction": float(w.opp_destruction or 0),
            "start_time": w.start_time,
            "end_time": w.end_time
        } for w in cwl_wars
    ]

@router.get("/donations")
def get_top_donations(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Ambil Top 5 donatur tertinggi
    top_donors = db.query(ClanMember).filter(
        ClanMember.clan_tag == server.clan_tag
    ).order_by(desc(ClanMember.donations)).limit(5).all()
    
    return [
        {
            "tag": m.tag,
            "name": m.name,
            "role": m.role,
            "donations": m.donations,
            "donations_received": m.donations_received
        } for m in top_donors
    ]

@router.get("/inactive")
def get_inactive_members(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # Ambil 10 member dengan donasi terendah (indikasi pasif)
    inactive = db.query(ClanMember).filter(
        ClanMember.clan_tag == server.clan_tag
    ).order_by(ClanMember.donations).limit(10).all()
    
    return [
        {
            "tag": m.tag,
            "name": m.name,
            "role": m.role,
            "donations": m.donations,
            "last_updated": m.last_updated
        } for m in inactive
    ]
