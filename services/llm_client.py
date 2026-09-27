import os
import logging
import asyncio
from google import genai
from google.genai import types
from services.db import get_db
from models import ClanMember, ServerConfig
from datetime import datetime

logger = logging.getLogger('bot.llm')

def _check_pro_access(guild_id: str):
    db = get_db()
    try:
        config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(guild_id)).first()
        if not config:
            return None, "❌ Server ini belum di-setup! Gunakan `/setup` terlebih dahulu."
        
        now = datetime.now()
        tier_status = str(config.tier).lower() if config.tier else "free"
        is_tier_pro = tier_status in ["pro", "ai_pro"]
        is_not_expired = (config.expired_at is None) or (config.expired_at > now)
        
        if not (is_tier_pro and is_not_expired):
            return None, (
                "⚠️ **Akses AI Pro Belum Aktif**\n"
                "Fitur analisis mendalam ini khusus untuk **Tier AI Pro** (Rp30.000/bulan).\n"
                "Hubungi Admin Ixiera (`ixiera.id`) untuk upgrade lisensi server kamu!"
            )
        return config, None
    finally:
        db.close()

async def run_ai_audit(guild_id: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "❌ API Key AI belum dikonfigurasi."

    config, err_msg = _check_pro_access(guild_id)
    if err_msg:
        return err_msg

    db = get_db()
    try:
        clan_tag = config.clan_tag
        members = db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).all()
        if not members:
            return f"❌ Data member untuk clan `{clan_tag}` belum tersinkronisasi."

        total_members = len(members)
        total_donations = sum(m.donations for m in members)
        avg_donations = total_donations // total_members if total_members > 0 else 0
        
        zero_donors = [m for m in members if m.donations == 0]
        top_donors = sorted(members, key=lambda x: x.donations, reverse=True)[:5]
        low_donors = sorted(members, key=lambda x: x.donations)[:5]

        context = f"METRICS CLAN ({clan_tag}):\n"
        context += f"- Total Member: {total_members}/50\n"
        context += f"- Rata-rata Donasi Clan: {avg_donations}\n"
        context += f"- Top Donatur: {', '.join([f'{m.name} ({m.donations})' for m in top_donors])}\n"
        context += f"- Donasi 0 ({len(zero_donors)} member): {', '.join([m.name for m in zero_donors[:10]])}\n"
        context += f"- Sample Member Donasi Terendah: {', '.join([f'{m.name} (TH{m.townhall_level}, {m.donations} donasi)' for m in low_donors])}\n"
    finally:
        db.close()

    prompt = (
        "Lu adalah Niki, Konsultan AI Manajemen Clan Clash of Clans dari ixiera.id.\n"
        "Gunakan gaya bahasa yang humble, suportif, dan bersahabat layaknya seorang mentor.\n"
        "Fokuslah pada pembinaan member. JANGAN menyarankan kick secara agresif, berikan saran teguran halus atau cara leader merangkul member yang sedang pasif/sibuk di dunia nyata.\n\n"
        f"{context}\n\n"
        "Beri format respons yang rapi menggunakan emoji Discord:\n"
        "1. 📊 **Kesehatan Clan** (Skor 1-10 + evaluasi positif/suportif)\n"
        "2. 🤝 **Fokus Pembinaan** (Sebutkan member pasif & saran pendekatan personal ke mereka)\n"
        "3. 💡 **Action Plan Minggu Ini** (Saran ringan dan membangun untuk Leader/Co-Leader)"
    )

    client = genai.Client(api_key=api_key)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(model='gemini-3.6-flash', contents=prompt)
            return response.text
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            logger.error(f"Error AI Audit: {e}")
            return "❌ Server AI sedang kelebihan beban. Mohon coba beberapa menit lagi."

async def run_war_strategy(guild_id: str, war_data: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "❌ API Key AI belum dikonfigurasi."

    config, err_msg = _check_pro_access(guild_id)
    if err_msg:
        return err_msg

    if not war_data or war_data.get('state') not in ['inWar', 'preparation']:
        return "🛡️ Clan sedang tidak dalam persiapan war atau perang aktif."

    clan = war_data.get('clan', {})
    opponent = war_data.get('opponent', {})
    
    context = (
        f"WAR DATA:\n"
        f"Status: {war_data.get('state')}\n"
        f"Clan Kita ({clan.get('name')}): {clan.get('stars')} Bintang, {clan.get('destructionPercentage')}% Destruction\n"
        f"Lawan ({opponent.get('name')}): {opponent.get('stars')} Bintang, {opponent.get('destructionPercentage')}% Destruction\n"
        f"Jumlah Pemain Per Perang: {war_data.get('teamSize')} vs {war_data.get('teamSize')}\n"
    )

    prompt = (
        "Lu adalah Niki, War Strategist CoC dari ixiera.id yang humble.\n"
        "Berdasarkan kondisi agregat perang di bawah ini, berikan saran taktik rotasi serangan secara objektif:\n\n"
        f"{context}\n\n"
        "Beri format respons:\n"
        "1. ⚔️ **Analisis Posisi War** (Siapa yang unggul)\n"
        "2. 🎯 **Fokus Strategi Clan** (Kapan harus mirror, kapan harus clean-up bawah)\n"
        "3. 📢 **Draf Pesan Broadcast Chat In-Game** (Pesan pendek suportif untuk Leader ke chat CoC)"
    )

    client = genai.Client(api_key=api_key)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(model='gemini-3.6-flash', contents=prompt)
            return response.text
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            logger.error(f"Error War Strategy: {e}")
            return "❌ Server AI sedang kelebihan beban. Mohon coba beberapa menit lagi."

# FUNGSI VISION: Screenshot Base + Opsional Input Combo/Pasukan
async def run_visual_strategy(guild_id: str, image_bytes: bytes, detail_pasukan: str = None) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "❌ API Key AI belum dikonfigurasi."

    config, err_msg = _check_pro_access(guild_id)
    if err_msg:
        return err_msg

    info_pasukan = f"\nINFO PASUKAN / EQUIPMENT ATTACKER:\n{detail_pasukan}\n" if detail_pasukan else ""

    prompt = (
        "Lu adalah Niki, War Strategist Clash of Clans yang humble dan suportif dari ixiera.id.\n"
        "Leader baru saja mengirimkan screenshot base lawan yang akan diserang."
        f"{info_pasukan}\n"
        "Analisis gambar base tersebut (dan pertimbangkan info pasukan/equipment jika dicantumkan). Format respons:\n"
        "1. 🏰 **Analisis Base Lawan** (Titik lemah, posisi Town Hall, Eagle Artillery, Inferno, Monolith, dll)\n"
        "2. 🎯 **Rekomendasi Entry Point & Taktik** (Saran eksekusi terbaik menggunakan meta terkini atau pasukan yang dimiliki)\n"
        "3. 📢 **Saran Eksekusi Hero & Spell** (Tips timing skill hero/equipment dan pemakaian spell)"
    )

    client = genai.Client(api_key=api_key)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model='gemini-3.6-flash',
                contents=[types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'), prompt]
            )
            return response.text
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            logger.error(f"Error Visual Strategy: {e}")
            return "❌ Server AI sedang kelebihan beban. Mohon coba beberapa menit lagi."
