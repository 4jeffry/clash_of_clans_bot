import os
import logging
from google import genai
from services.db import get_db
from models import ClanMember, ServerConfig
from datetime import datetime

logger = logging.getLogger('bot.llm')

def _check_pro_access(guild_id: str):
    """Mengecek apakah server memiliki akses Tier AI Pro yang aktif"""
    db = get_db()
    try:
        config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(guild_id)).first()
        if not config:
            return None, "❌ Server ini belum di-setup! Gunakan `/setup` terlebih dahulu."
        
        now = datetime.now()
        is_pro = (config.tier == "ai_pro" and config.expired_at and config.expired_at > now)
        if not is_pro:
            return None, (
                "⚠️ **Akses AI Pro Belum Aktif**\n"
                "Fitur analisis mendalam ini khusus untuk **Tier AI Pro** (Rp30.000/bulan).\n"
                "Hubungi Admin Ixiera (`ixiera.id`) untuk upgrade lisensi server kamu!"
            )
        return config, None
    finally:
        db.close()

async def run_ai_audit(guild_id: str) -> str:
    """Melakukan deep audit kesehatan clan berdasarkan snapshot database SQL"""
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
            return f"❌ Data member untuk clan `{clan_tag}` belum tersinkronisasi di database."

        total_members = len(members)
        total_donations = sum(m.donations for m in members)
        avg_donations = total_donations // total_members if total_members > 0 else 0
        
        zero_donors = [m for m in members if m.donations == 0]
        top_donors = sorted(members, key=lambda x: x.donations, reverse=True)[:5]
        low_donors = sorted(members, key=lambda x: x.donations)[:5]

        # Ingestion context ringkas
        context = f"METRICS CLAN ({clan_tag}):\n"
        context += f"- Total Member: {total_members}/50\n"
        context += f"- Rata-rata Donasi Clan: {avg_donations}\n"
        context += f"- Top Donatur: {', '.join([f'{m.name} ({m.donations})' for m in top_donors])}\n"
        context += f"- Donasi 0 ({len(zero_donors)} member): {', '.join([m.name for m in zero_donors[:10]])}\n"
        context += f"- Sample Member Donasi Terendah: {', '.join([f'{m.name} (TH{m.townhall_level}, {m.donations} donasi)' for m in low_donors])}\n"
    finally:
        db.close()

    prompt = (
        "Lu adalah Anis, Konsultan AI Manajemen Clan Clash of Clans Profesional dari ixiera.id.\n"
        "Analisis data statistik clan berikut secara lugas, objektif, dan berikan panduan konkret untuk Leader:\n\n"
        f"{context}\n\n"
        "Beri format respons yang rapi menggunakan emoji Discord:\n"
        "1. 📊 **Health Check Clan** (Skor 1-10 + analisis ringkas kondisi keaktifan)\n"
        "2. ⚠️ **Rekomendasi Kick / Peringatan** (Sebutkan nama-nama yang indikasi pasif/pensi beserta alasannya)\n"
        "3. 💡 **Action Plan Minggu Ini** (Saran konkret buat Leader/Co-Leader)"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        logger.error(f"Error AI Audit: {e}")
        return "❌ Gagal memproses AI Audit. Coba beberapa saat lagi."

async def run_war_strategy(guild_id: str, war_data: dict) -> str:
    """Menganalisis data war aktif dari API dan memberikan saran taktik"""
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
        "Lu adalah Anis, War General / Strategist CoC dari ixiera.id.\n"
        "Berdasarkan kondisi perang di bawah ini, berikan saran taktik rotasi serangan yang harus diinstruksikan Leader ke clan:\n\n"
        f"{context}\n\n"
        "Beri format respons:\n"
        "1. ⚔️ **Analisis Posisi War**\n"
        "2. 🎯 **Fokus Strategi Serangan** (Kapan harus mirror, kapan harus clean-up bawah)\n"
        "3. 📢 **Draf Pesan Broadcast Chat In-Game** (Pesan pendek yang tinggal di-copas Leader ke chat CoC)"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        logger.error(f"Error War Strategy: {e}")
        return "❌ Gagal memproses War Strategy AI."
