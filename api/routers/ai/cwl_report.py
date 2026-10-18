from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.deps import get_active_server, get_db
from .utils import disable_prepare

router = APIRouter()

@router.get("/cwl-report")
def get_cwl_report(server = Depends(get_active_server), db: Session = Depends(get_db)):
    disable_prepare(db)
    
    # 1. Cari semua war yang is_cwl = true
    cwl_wars = db.execute(
        text("SELECT id FROM wars WHERE clan_tag = :ctag AND is_cwl = true"), 
        {"ctag": server.clan_tag}
    ).fetchall()
    
    if not cwl_wars:
        return {"error": "Belum ada data CWL di database. (Pastikan bot sudah menyinkronkan data CWL)."}
        
    war_ids = [w.id for w in cwl_wars]
    war_ids_str = f"({','.join(map(str, war_ids))})"
    
    # 2. Query Statistik (CTE biar gak double count attacks)
    query = text(f"""
        WITH player_stars AS (
            SELECT attacker_tag, war_id, SUM(stars) as stars
            FROM war_attacks
            WHERE war_id IN {war_ids_str}
            GROUP BY attacker_tag, war_id
        )
        SELECT 
            wp.player_name, 
            wp.townhall_level,
            COALESCE(SUM(ps.stars), 0) as total_stars,
            SUM(wp.attacks_used) as total_attacks_used,
            SUM(wp.attacks_allowed) as total_attacks_allowed
        FROM war_participants wp
        LEFT JOIN player_stars ps ON wp.player_tag = ps.attacker_tag AND wp.war_id = ps.war_id
        WHERE wp.war_id IN {war_ids_str}
        GROUP BY wp.player_tag, wp.player_name, wp.townhall_level
        ORDER BY total_stars DESC
    """)
    
    results = db.execute(query).fetchall()
    
    stats = []
    total_klan_bintang = 0
    for r in results:
        bintang = int(r.total_stars or 0)
        total_klan_bintang += bintang
        used = int(r.total_attacks_used or 0)
        allowed = int(r.total_attacks_allowed or 0)
        
        stats.append({
            "name": r.player_name,
            "th": r.townhall_level,
            "stars": bintang,
            "attacks_used": used,
            "attacks_allowed": allowed,
            "is_slacker": used == 0
        })

    mvp = stats[:3]
    slackers = [s for s in stats if s['is_slacker']]
    total_attacks_used = sum(s['attacks_used'] for s in stats)
    total_attacks_allowed = sum(s['attacks_allowed'] for s in stats)
    efficiency = round((total_attacks_used / total_attacks_allowed) * 100, 1) if total_attacks_allowed > 0 else 0

    return {
        "total_wars": len(war_ids),
        "total_klan_bintang": total_klan_bintang,
        "efficiency": efficiency,
        "mvp": mvp,
        "slackers": slackers,
        "full_stats": stats
    }
