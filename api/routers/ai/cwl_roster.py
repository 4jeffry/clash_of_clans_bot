from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.deps import get_active_server, get_db
from models import ClanMember, War
from sqlalchemy import desc
from .utils import disable_prepare

router = APIRouter()

@router.get("/cwl-roster")
def get_cwl_roster(server = Depends(get_active_server), db: Session = Depends(get_db)):
    disable_prepare(db)
    
    # 1. Ambil semua member
    members = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()
    
    # 2. Cari War terakhir yang udah selesai buat narik bintang
    latest_war = db.query(War).filter(War.clan_tag == server.clan_tag, War.state == 'warEnded').order_by(desc(War.id)).first()
    
    stars_map = {}
    if latest_war:
        # Tarik total bintang per player di war terakhir
        attacks = db.execute(
            text("SELECT attacker_tag, SUM(stars) FROM war_attacks WHERE war_id = :wid GROUP BY attacker_tag"), 
            {"wid": latest_war.id}
        ).fetchall()
        stars_map = {row[0]: row[1] for row in attacks}

    result = []
    for m in members:
        result.append({
            "tag": m.tag,
            "name": m.name,
            "th": m.townhall_level or 0,
            "donations": m.donations or 0,
            "role": m.role,
            "war_stars": stars_map.get(m.tag, 0)
        })
    
    # 3. Urutkan (Sorting): 
    # Prioritas 1: TH Tertinggi
    # Prioritas 2: Bintang War Terbanyak
    # Prioritas 3: Donasi Terbanyak
    result = sorted(result, key=lambda x: (x['th'], x['war_stars'], x['donations']), reverse=True)
    
    return result
