import os
import logging
import asyncio
from google import genai
from services.db import get_db
from models import ClanMember, ServerConfig
from datetime import datetime
from collections import Counter

logger = logging.getLogger('bot.llm')

def _check_pro_access(guild_id: str):
    db = get_db()
    try:
        config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(guild_id)).first()
        if not config:
            return None, "❌ Server belum di-setup."
        now = datetime.now()
        is_tier_pro = str(config.tier).lower() in ["pro", "ai_pro"] if config.tier else False
        is_not_expired = (config.expired_at is None) or (config.expired_at > now)
        if not (is_tier_pro and is_not_expired):
            return None, "⚠️ **Akses AI Pro Belum Aktif.** Hubungi Admin ixiera.id."
        return config, None
    finally:
        db.close()

async def _generate_with_fallback(client, contents):
    models_to_try = ['gemini-3.8-flash']
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = await client.aio.models.generate_content(model=model_name, contents=contents)
                return response.text
            except Exception as e:
                error_msg = str(e).upper()
                if "503" in error_msg or "UNAVAILABLE" in error_msg or "429" in error_msg:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                logger.warning(f"Model {model_name} gagal: {e}")
                break 
    return "SERVER AI MENGALAMI GANGGUAN. SILAKAN COBA LAGI NANTI."

def _get_base_prompt():
    return (
        "Anda adalah Niki, Executive AI System by ixiera.id. "
        "ATURAN MUTLAK: Jawaban harus berupa TEKS POLOS (Plain Text) yang sangat rapi untuk cetak PDF. "
        "DILARANG KERAS menggunakan simbol Markdown seperti bintang (**) atau pagar (#). "
        "Gunakan HURUF KAPITAL untuk semua judul atau nama kategori. "
        "Jawaban harus sangat singkat, padat, dan jelas. Maksimal 2 kalimat per poin. "
        "Gunakan simbol ( - ) untuk list/bullet points. "
        "DILARANG menggunakan kata pengantar, sapaan, atau penutup. Langsung berikan laporan intinya."
    )

async def run_ai_audit(guild_id: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "API KEY BELUM DIKONFIGURASI."
    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    db = get_db()
    try:
        clan_tag = config.clan_tag
        members = db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).all()
        if not members: return "DATA MEMBER BELUM TERSINKRONISASI."

        total_members = len(members)
        total_donations = sum(m.donations for m in members)
        avg_donations = total_donations // total_members if total_members > 0 else 0
        zero_donors = [m.name for m in members if m.donations == 0][:15]
        top_donors = [f"{m.name} ({m.donations})" for m in sorted(members, key=lambda x: x.donations, reverse=True)[:5]]
        th_levels = Counter([m.townhall_level for m in members if m.townhall_level])
        th_summary = ", ".join([f"TH{th}: {count}" for th, count in sorted(th_levels.items(), reverse=True)])
    finally:
        db.close()

    prompt = f"""
    {_get_base_prompt()}
    DATA KLAN:
    Member: {total_members}/50
    TH: {th_summary}
    Rata-rata Donasi: {avg_donations}
    Top Donatur: {', '.join(top_donors)}
    Pasif: {', '.join(zero_donors)}

    FORMAT OUTPUT:
    AUDIT KESEHATAN KLAN

    1. STATUS UTAMA
    [Isi dengan 1 kalimat skor persentase kesehatan klan]

    2. EVALUASI MEMBER
    [Isi dengan 1 kalimat evaluasi member]

    3. ACTION PLAN
    [Isi dengan 2 poin instruksi singkat]
    """
    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)

async def run_ai_scout(guild_id: str, war_data: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "API KEY BELUM DIKONFIGURASI."
    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    opponent = war_data.get('opponent', {})
    members = opponent.get('members', [])
    opp_th_levels = Counter([m.get('townhallLevel', 0) for m in members if m.get('townhallLevel')])
    opp_th_summary = ", ".join([f"TH{th}: {count}" for th, count in sorted(opp_th_levels.items(), reverse=True)])

    prompt = f"""
    {_get_base_prompt()}
    DATA MUSUH:
    Klan: {opponent.get('name')}
    Roster TH: {opp_th_summary}

    FORMAT OUTPUT:
    INTEL ROSTER LAWAN: {opponent.get('name')}

    1. BOBOT PERANG
    [Isi dengan 1 baris simpulan kekuatan musuh]

    2. STRATEGI EKSEKUSI
    [Isi dengan 2 poin instruksi pembagian target TH]

    3. TITIK KRITIS
    [Isi dengan 1 baris peringatan ke member]
    """
    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)

async def run_war_strategy(guild_id: str, war_data: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "API KEY BELUM DIKONFIGURASI."
    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    clan = war_data.get('clan', {})
    opponent = war_data.get('opponent', {})
    
    prompt = f"""
    {_get_base_prompt()}
    STATUS PERANG:
    Kita ({clan.get('name')}): {clan.get('stars')} Bintang, {clan.get('destructionPercentage')}% Dest, {clan.get('attacks', 0)} Serangan Terpakai
    Lawan ({opponent.get('name')}): {opponent.get('stars')} Bintang, {opponent.get('destructionPercentage')}% Dest, {opponent.get('attacks', 0)} Serangan Terpakai

    FORMAT OUTPUT:
    STRATEGI PERANG AKTIF

    1. POSISI SAAT INI
    [Isi dengan 1 baris simpulan dominasi skor]

    2. TAKTIK LANJUTAN
    [Isi dengan 2 poin fokus clean-up bawah atau hajar atas]

    3. BROADCAST IN-GAME
    [Isi dengan 1 kalimat untuk di-copas leader]
    """
    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)

async def run_ai_report(guild_id: str, latest_war_log: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "API KEY BELUM DIKONFIGURASI."
    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    clan = latest_war_log.get('clan', {})
    opponent = latest_war_log.get('opponent', {})
    result = latest_war_log.get('result', 'unknown')

    prompt = f"""
    {_get_base_prompt()}
    DATA PASCA-PERANG:
    Hasil: {result} vs {opponent.get('name')}
    Skor Kita: {clan.get('stars')} Bintang ({clan.get('destructionPercentage')}%) | Serangan: {clan.get('attacks', 0)}
    Skor Musuh: {opponent.get('stars')} Bintang ({opponent.get('destructionPercentage')}%)

    FORMAT OUTPUT:
    LAPORAN EVALUASI PASCA-PERANG

    1. REVIEW EKSEKUTIF
    [Isi dengan 1 baris alasan utama hasil war]

    2. EVALUASI EFISIENSI
    [Isi dengan 2 poin ringkas pemakaian serangan]

    3. REKOMENDASI
    [Isi dengan 1 baris perbaikan ke depan]
    """
    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)

async def run_ai_screen(guild_id: str, player_data: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "API KEY BELUM DIKONFIGURASI."
    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    name = player_data.get('name', 'Unknown')
    th = player_data.get('townHallLevel', 0)
    donations = player_data.get('donations', 0)
    received = player_data.get('donationsReceived', 0)
    war_stars = player_data.get('warStars', 0)

    prompt = f"""
    {_get_base_prompt()}
    PROFIL CALON MEMBER:
    Nama: {name} (TH {th})
    Donasi Keluar: {donations} | Diterima: {received}
    War Stars: {war_stars}

    FORMAT OUTPUT:
    INTEL SCREENING: {name}

    1. LOYALITAS DAN RASIO
    [Isi dengan 1 baris kesimpulan donasi]

    2. PENGALAMAN WAR
    [Isi dengan 1 baris analisis bintang war]

    3. KESIMPULAN AKHIR
    [TERIMA / PANTAU / TOLAK] - [Alasan singkat]
    """
    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)

async def run_ai_opponent(guild_id: str, clan_tag: str, war_data: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "API KEY BELUM DIKONFIGURASI."
    config, err_msg = _check_pro_access(guild_id)
    if err_msg: return err_msg

    opponent = war_data.get('opponent', {})
    opp_tag = opponent.get('tag')
    from services.coc_client import CoCClient
    opp_info = await CoCClient().get_clan_info(opp_tag)

    prompt = f"""
    {_get_base_prompt()}
    DATA LAWAN:
    Klan: {opponent.get('name')}
    Level: {opp_info.get('clanLevel', 'N/A') if opp_info else 'N/A'}
    Win Streak: {opp_info.get('warWinStreak', 0) if opp_info else 'N/A'}
    War Wins: {opp_info.get('warWins', 0) if opp_info else 'N/A'}

    FORMAT OUTPUT:
    ESTIMASI PELUANG MENANG: {opponent.get('name')}

    1. KEKUATAN MUSUH
    [Isi dengan 1 baris analisis level dan streak musuh]

    2. ESTIMASI PROBABILITAS
    [Isi dengan Angka % dan 1 baris argumen]

    3. SIKAP OPERASIONAL
    [Isi dengan 1 baris peringatan]
    """
    client = genai.Client(api_key=api_key)
    return await _generate_with_fallback(client, prompt)
