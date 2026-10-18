from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.deps import get_active_server, get_db
from models import ServerConfig, ClanMember
from api.services.web_ai import generate_narrative, get_base_prompt
from collections import Counter

router = APIRouter()

@router.get("/audit")
def get_audit_rule_based(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # 1. Ambil data statistik
    members = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()
    if not members:
        return {"error": "Belum ada data member."}

    total_members = len(members)
    total_donations = sum(m.donations for m in members)
    avg_donations = total_donations // total_members if total_members > 0 else 0
    zero_donors = [m.name for m in members if m.donations == 0]
    top_donors = [{"name": m.name, "score": m.donations} for m in sorted(members, key=lambda x: x.donations, reverse=True)[:3]]
    th_levels = Counter([m.townhall_level for m in members if m.townhall_level])
    th_summary = [{"th": th, "count": count} for th, count in sorted(th_levels.items(), reverse=True)]

    # 2. Bikin Narasi Template (Rule-based)
    health_pct = min(100, int((avg_donations / 500) * 100)) if avg_donations > 0 else 0
    
    narrative = f"STATUS UTAMA:\n- Kesehatan klan diperkirakan {health_pct}% berdasarkan rata-rata donasi.\n\n"
    narrative += f"EVALUASI MEMBER:\n- Total {total_members} member dengan rata-rata donasi {avg_donations}.\n"
    narrative += f"- Ditemukan {len(zero_donors)} member pasif (donasi 0).\n\n"
    narrative += f"ACTION PLAN:\n- Berikan apresiasi ke Top Donatur ({top_donors[0]['name']}).\n- Evaluasi member pasif untuk rotasi war."

    return {
        "raw_data": {
            "total_members": total_members,
            "avg_donations": avg_donations,
            "zero_donors_count": len(zero_donors),
            "top_donors": top_donors,
            "th_summary": th_summary
        },
        "narrative": narrative,
        "credits": server.ai_credits
    }

@router.post("/audit/enhance")
async def enhance_audit(server = Depends(get_active_server), db: Session = Depends(get_db)):
    # 1. Cek Kredit
    if not server.ai_credits or server.ai_credits <= 0:
        raise HTTPException(status_code=402, detail="Kredit AI Anda habis. Silakan top up.")

    # 2. Ambil data (mirip rule-based)
    members = db.query(ClanMember).filter(ClanMember.clan_tag == server.clan_tag).all()
    total_members = len(members)
    avg_donations = sum(m.donations for m in members) // total_members if total_members > 0 else 0
    zero_donors = [m.name for m in members if m.donations == 0][:10]
    top_donors = [f"{m.name} ({m.donations})" for m in sorted(members, key=lambda x: x.donations, reverse=True)[:5]]
    th_levels = Counter([m.townhall_level for m in members if m.townhall_level])
    th_summary = ", ".join([f"TH{th}: {count}" for th, count in sorted(th_levels.items(), reverse=True)])

    # 3. Prompt Gemini
    prompt = f"""
    {get_base_prompt()}
    DATA KLAN:
    Member: {total_members}/50
    TH: {th_summary}
    Rata-rata Donasi: {avg_donations}
    Top Donatur: {', '.join(top_donors)}
    Pasif: {', '.join(zero_donors)}

    FORMAT OUTPUT:
    AUDIT KESEHATAN KLAN

    1. STATUS UTAMA
    [1 kalimat skor kesehatan]

    2. EVALUASI MEMBER
    [1 kalimat evaluasi]

    3. ACTION PLAN
    [2 poin instruksi singkat]
    """
    
    # 4. Panggil AI & Kurangi Kredit
    result_text = await generate_narrative(prompt)
    
    # Kurangi kredit
    server.ai_credits -= 1
    db.commit()

    return {
        "narrative": result_text,
        "credits": server.ai_credits
    }
