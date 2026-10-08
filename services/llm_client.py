import os
import logging
import asyncio
from google import genai
from services.db import get_db
from models import ClanMember, ServerConfig, WarHistory
from datetime import datetime
from collections import Counter

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
                "Hubungi Admin ixiera.id untuk upgrade lisensi server kamu!\n"
                "💬 WA: https://wa.me/6285736048626"
            )
        return config, None
    finally:
        db.close()

async def _generate_with_fallback(client, contents):
    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash']
    max_retries = 3
    
    for model_name in models_to_try:
        for attempt in range(max_retries):
            try:
                response = await client.aio.models.generate_content(model=model_name, contents=contents)
                return response.text
            except Exception as e:
                error_msg = str(e).upper()
                if "503" in error_msg or "UNAVAILABLE" in error_msg or "429" in error_msg or "TOO_MANY_REQUESTS" in error_msg:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                logger.warning(f"Model {model_name} gagal: {e}. Fallback...")
                break 
                
    logger.error("Semua model AI gagal merespons.")
    return "❌ Server AI Google sedang mengalami gangguan. Coba beberapa saat lagi."

async def run_ai_audit(guild_id: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "❌ API Key AI belum dikonfigurasi."

    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    db = get_db()
    try:
        clan_tag = config.clan_tag
        members = db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).all()
        if not members:
            return f"❌ Data member untuk clan `{clan_tag}` belum tersinkronisasi di database. Tunggu proses background sync."

        total_members = len(members)
        total_donations = sum(m.donations for m in members)
        avg_donations = total_donations // total_members if total_members > 0 else 0
        
        zero_donors = [m for m in members if m.donations == 0]
        top_donors = sorted(members, key=lambda x: x.donations, reverse=True)[:5]
        
        th_levels = Counter([m.townhall_level for m in members if m.townhall_level])
        th_summary = ", ".join([f"TH{th}: {count}" for th, count in sorted(th_levels.items(), reverse=True)])

        context = (
            f"METRICS LOKAL CLAN ({clan_tag}):\n"
            f"- Total Member: {total_members}/50\n"
            f"- Komposisi TH: {th_summary}\n"
            f"- Rata-rata Donasi: {avg_donations}\n"
            f"- Top Donatur: {', '.join([f'{m.name} ({m.donations})' for m in top_donors])}\n"
            f"- Donasi 0 ({len(zero_donors)} member): {', '.join([m.name for m in zero_donors[:10]])}\n"
        )
    finally:
        db.close()

    prompt = (
        "Lu adalah Niki, Konsultan AI Manajemen Clan buatan ixiera.id.\n"
        "Gaya bahasa lu: Santai, suportif, tapi tajam menganalisis data klan.\n\n"
        f"{context}\n\n"
        "Beri evaluasi:\n"
        "1. 📊 **Status Kesehatan Clan** (Skor 1-100% dari aktivitas donasi & sebaran TH)\n"
        "2. 🤝 **Evaluasi Member** (Apresiasi penggendong klan, dan saran cara logis negur parasit tanpa bikin toxic)\n"
        "3. 💡 **Saran Action Plan Leader** (Langkah konkret minggu ini)"
    )

    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)

async def run_ai_scout(guild_id: str, war_data: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "❌ API Key AI belum dikonfigurasi."

    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    opponent = war_data.get('opponent', {})
    members = opponent.get('members', [])
    
    # Extract TH composition directly from war data
    opp_th_levels = Counter([m.get('townhallLevel', 0) for m in members if m.get('townhallLevel')])
    opp_th_summary = ", ".join([f"TH{th}: {count}" for th, count in sorted(opp_th_levels.items(), reverse=True)])

    prompt = f"""
    Lu adalah Niki, Analis Perang Esports CoC.
    Tugas lu menganalisis pertahanan klan musuh berdasarkan roster Town Hall mereka yang ikut war/CWL.

    Data Musuh:
    - Nama Clan: {opponent.get('name')}
    - Roster Town Hall: {opp_th_summary if opp_th_summary else "Data TH disembunyikan / tidak sinkron."}

    Format Output:
    ⚔️ **Intel Roster Lawan — {opponent.get('name')}**
    ⚖️ **Analisis Bobot Perang:** [Analisis logis apakah roster mereka berat di Top-TH atau merata]
    🎯 **Strategi Eksekusi Target:** [Saran tegas ke member kita, misal: "Pastikan TH15 sapu bersih TH14 musuh", dll]
    ⚠️ **Titik Kritis:** [Peringatan untuk member agar tidak blunder salah pilih musuh]
    """

    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)

async def run_war_strategy(guild_id: str, war_data: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "❌ API Key AI belum dikonfigurasi."

    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    if not war_data or war_data.get('state') not in ['inWar', 'preparation']:
        return "🛡️ Clan sedang tidak dalam perang aktif atau CWL."

    clan = war_data.get('clan', {})
    opponent = war_data.get('opponent', {})
    
    context = (
        f"WAR DATA:\nStatus: {war_data.get('state')}\n"
        f"Kita ({clan.get('name')}): {clan.get('stars')} Bintang, {clan.get('destructionPercentage')}% Dest\n"
        f"Lawan ({opponent.get('name')}): {opponent.get('stars')} Bintang, {opponent.get('destructionPercentage')}% Dest\n"
        f"Serangan Terpakai: {clan.get('attacks', 0)} (Kita) vs {opponent.get('attacks', 0)} (Lawan)\n"
    )

    prompt = (
        "Lu adalah Niki, War Strategist CoC.\n"
        "Berikan evaluasi taktik rotasi serangan secara objektif di tengah perang berjalan:\n\n"
        f"{context}\n\n"
        "Beri format respons:\n"
        "1. ⚔️ **Status Posisi** (Siapa yang lagi mendominasi dari skor & efisiensi serang)\n"
        "2. 🎯 **Taktik Bertahan/Menyerang** (Apakah fokus nabung attack buat akhir, clean-up bintang kecil, atau hajar atas)\n"
        "3. 📢 **Pesan Tempur In-Game** (1 kalimat tajam buat Leader copas ke chat klan)"
    )

    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)

async def run_ai_report(guild_id: str, latest_war_log: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "❌ API Key AI belum dikonfigurasi."

    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    if not latest_war_log:
        return "🛡️ Tidak ada data histori perang (War Log) yang bisa dianalisis."

    clan = latest_war_log.get('clan', {})
    opponent = latest_war_log.get('opponent', {})
    result = latest_war_log.get('result', 'unknown')

    context = (
        f"REPORT PASCA-WAR:\n"
        f"Hasil: Kita {result} melawan {opponent.get('name')}\n"
        f"Skor Akhir: {clan.get('stars')}⭐ ({clan.get('destructionPercentage')}%) VS {opponent.get('stars')}⭐ ({opponent.get('destructionPercentage')}%)\n"
        f"Total Serangan Dipakai: {clan.get('attacks', 0)}\n"
    )

    prompt = f"""
    Lu adalah Niki, Esports Analyst Clash of Clans.
    Buat ulasan pasca-pertandingan (Post-Match Report) dari data ini:
    {context}

    Format Output:
    📝 **Laporan Intel Pasca-Perang**
    🏆 **Review Pertandingan:** [Ulas dengan tajam kenapa kita Menang/Kalah/Seri berdasarkan statistik bintang & destruksi tersebut]
    💡 **Evaluasi Eksekusi:** [Berikan 2 baris evaluasi teknis yang masuk akal terkait efisiensi pemakaian jatah serangan]
    🎯 **Saran Untuk War Berikutnya:** [1 kalimat saran latihan atau disiplin untuk member]
    """

    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)

async def run_ai_screen(guild_id: str, player_data: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "❌ API Key AI belum dikonfigurasi."

    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    name = player_data.get('name', 'Unknown')
    tag = player_data.get('tag', '')
    th = player_data.get('townHallLevel', 0)
    donations = player_data.get('donations', 0)
    received = player_data.get('donationsReceived', 0)
    war_stars = player_data.get('warStars', 0)
    heroes = player_data.get('heroes', [])

    hero_info = ", ".join([f"{h['name']} (Lv {h['level']})" for h in heroes if h.get('village') == 'home'])

    prompt = f"""
    Kamu AI Rekrutmen Clan. Analisis profil ini:\n
    Nama: {name} | TH: {th} | War Stars: {war_stars}\n
    Donasi Keluar: {donations} | Masuk: {received}\n
    Level Hero: {hero_info}\n
    
    Output:\n
    🔍 **Intel Rekrutmen — {name}** (TH {th})\n
    • **Rasio Donasi:** [Analisis pelit/dermawan]\n
    • **Kematangan Akun:** [Apakah level hero sesuai dengan standar TH tersebut atau prematur]\n
    📌 **Verdict Akhir:** [🟢 GASS TERIMA / ⚠️ PANTAU DULU / 🔴 TOLAK]
    """

    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)

async def run_ai_opponent(guild_id: str, clan_tag: str, war_data: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "❌ API Key AI belum dikonfigurasi."

    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    opponent = war_data.get('opponent', {})
    opp_tag = opponent.get('tag')
    
    from services.coc_client import CoCClient
    coc_client = CoCClient()
    opp_info = await coc_client.get_clan_info(opp_tag)

    context = f"""
    Klan Kita vs {opponent.get('name')} ({opp_tag})
    Ukuran Tim: {war_data.get('teamSize')} vs {war_data.get('teamSize')}
    Level Klan Lawan: {opp_info.get('clanLevel', 'N/A') if opp_info else 'N/A'}
    Win Streak Lawan: {opp_info.get('warWinStreak', 0) if opp_info else 'N/A'}
    Total War Won Lawan: {opp_info.get('warWins', 0) if opp_info else 'N/A'}
    """

    prompt = f"""
    Kamu analis intelijen war. Baca statistik klan musuh ini:\n{context}\n
    Output:\n
    🎯 **Intel Lawan — {opponent.get('name')}**\n
    • **Ancaman Musuh:** [Analisis seberapa pro musuh berdasarkan level dan win streak mereka]\n
    • **Estimasi Peluang Menang:** [Berapa persen klan kita bisa menang secara teoretis, dan jelaskan argumen singkatnya]\n
    💡 **Sikap Prep Day:** [1 kalimat wejangan mental agar member tidak meremehkan musuh]
    """

    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)
