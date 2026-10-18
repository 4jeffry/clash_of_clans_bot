from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.deps import get_active_server, get_db
from models import ClanMember
from api.services.web_ai import generate_narrative, get_base_prompt
from collections import Counter
from .utils import get_ai_credits, deduct_ai_credit, save_ai_history

router = APIRouter()

@router.get("/audit")
def get_audit_rule_based(server = Depends(get_active_server), db: Session = Depends(get_db)):
    members = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()
    if not members:
        return {"error": "Belum ada data member."}

    total_members = len(members)
    total_donations = sum(m.donations for m in members)
    avg_donations = total_donations // total_members if total_members > 0 else 0
    zero_donors = [m.name for m in members if m.donations == 0]
    top_donors = [{"name": m.name, "score": m.donations} for m in sorted(members, key=lambda x: x.donations, reverse=True)[:5]]
    th_levels = Counter([m.townhall_level for m in members if m.townhall_level])
    th_summary = [{"th": th, "count": count} for th, count in sorted(th_levels.items(), reverse=True)]

    health_pct = min(100, int((avg_donations / 500) * 100)) if avg_donations > 0 else 0
    
    narrative = f"STATUS UTAMA:\n- Kesehatan klan diperkirakan {health_pct}% berdasarkan rata-rata donasi.\n\n"
    narrative += f"EVALUASI MEMBER:\n- Total {total_members} member dengan rata-rata donasi {avg_donations}.\n"
    narrative += f"- Ditemukan {len(zero_donors)} member pasif (donasi 0).\n\n"
    narrative += f"ACTION PLAN:\n- Berikan apresiasi ke Top Donatur ({top_donors[0]['name'] if top_donors else 'N/A'}).\n- Evaluasi member pasif untuk rotasi war."

    raw_data = {
        "total_members": total_members,
        "active_members": total_members - len(zero_donors),
        "zero_donors_count": len(zero_donors),
        "avg_donations": avg_donations,
        "top_donors": top_donors,
        "th_summary": th_summary
    }

    return {"raw_data": raw_data, "narrative": narrative, "credits": get_ai_credits(db, server.guild_id)}

@router.post("/audit/enhance")
async def enhance_audit(server = Depends(get_active_server), db: Session = Depends(get_db)):
    credits = get_ai_credits(db, server.guild_id)
    if credits <= 0:
        raise HTTPException(status_code=402, detail="Kredit AI Anda habis. Silakan top up.")

    members = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()
    if not members:
        raise HTTPException(status_code=404, detail="Belum ada data member untuk dianalisis.")

    total_members = len(members)
    avg_donations = sum(m.donations for m in members) // total_members if total_members > 0 else 0
    zero_donors = [m.name for m in members if m.donations == 0][:10]
    top_donors = [f"{m.name} ({m.donations})" for m in sorted(members, key=lambda x: x.donations, reverse=True)[:5]]
    
    prompt = f"{get_base_prompt()}\nDATA KLAN:\nMember: {total_members}/50\nRata-rata Donasi: {avg_donations}\nTop Donatur: {', '.join(top_donors)}\nPasif: {', '.join(zero_donors)}\n\nFORMAT OUTPUT:\nAUDIT KESEHATAN KLAN\n1. STATUS UTAMA\n2. EVALUASI MEMBER\n3. ACTION PLAN"
    result_text = await generate_narrative(prompt)
    deduct_ai_credit(db, server.guild_id)

    try:
        top_donors_dict = [{"name": m.name, "score": m.donations} for m in sorted(members, key=lambda x: x.donations, reverse=True)[:5]]
        raw_data = {"total_members": total_members, "active_members": total_members - len(zero_donors), "zero_donors_count": len(zero_donors), "avg_donations": avg_donations, "top_donors": top_donors_dict}
        save_ai_history(db, server.guild_id, "audit_enhance", raw_data, result_text.replace("<br>", "\n"))
    except Exception as e: print(f"Gagal simpan history: {e}")

    return {"narrative": result_text, "credits": get_ai_credits(db, server.guild_id)}
