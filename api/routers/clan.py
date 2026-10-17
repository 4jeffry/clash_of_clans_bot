from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
import httpx
import os
import urllib.parse
from api.deps import get_active_server, get_db
from models import War, ClanMember, WarHistory

router = APIRouter()
COC_TOKEN = os.getenv('COC_API_TOKEN')

async def fetch_coc(endpoint: str):
    if not COC_TOKEN: return None
    url = f"https://cocproxy.royaleapi.dev/v1{endpoint}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers={"Authorization": f"Bearer {COC_TOKEN}"})
        return res.json() if res.status_code == 200 else None

@router.get("/capital")
async def get_capital_info(server = Depends(get_active_server)):
    encoded_tag = urllib.parse.quote(server.clan_tag)
    data = await fetch_coc(f"/clans/{encoded_tag}/capitalraidseasons")
    
    if not data or "items" not in data or not data["items"]:
        return {"error": "Data Clan Capital tidak ditemukan."}
        
    latest = data["items"][0]
    return {
        "total_loot": latest.get('capitalTotalLoot', 0),
        "total_attacks": latest.get('totalAttacks', 0),
        "districts_destroyed": latest.get('enemyDistrictsDestroyed', 0),
        "defensive_rewards": latest.get('defensiveReward', 0),
        "completed_raids": latest.get('raidsCompleted', 0),
        "state": latest.get('state', 'ended')
    }

@router.get("/capitaldonations")
async def get_capital_donations(server = Depends(get_active_server)):
    encoded_tag = urllib.parse.quote(server.clan_tag)
    data = await fetch_coc(f"/clans/{encoded_tag}")
    
    if not data or "memberList" not in data:
        return []
        
    members = sorted(data["memberList"], key=lambda x: x.get("clanCapitalContributions", 0), reverse=True)[:10]
    return [{"name": m.get('name', 'Unknown'), "townhall": m.get('townHallLevel', 0), "contributions": m.get("clanCapitalContributions", 0)} for m in members]

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
