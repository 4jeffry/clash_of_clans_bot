import os
import logging
from google import genai
from services.db import get_db
from models import ClanMember, ServerConfig

logger = logging.getLogger('bot.llm')

def _get_clan_context_from_db(guild_id: str) -> str:
    """Mengambil snapshot data aktif dan pasif dari database berdasarkan server"""
    db = get_db()
    try:
        # 1. Cari clan tag berdasarkan ID Server Discord tempat bot diajak ngobrol
        config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(guild_id)).first()
        if not config:
            return "Informasi Sistem: Server ini belum melakukan !setup clan."
            
        clan_tag = config.clan_tag
        
        # 2. Ambil Top 5 Member Paling Aktif (Donasi Tertinggi)
        top_members = db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).order_by(ClanMember.donations.desc()).limit(5).all()
        
        # 3. Ambil Top 5 Member Paling Pasif (Donasi 0 / Terendah)
        lazy_members = db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).order_by(ClanMember.donations.asc()).limit(5).all()

        if not top_members:
            return f"Data member untuk clan {clan_tag} belum tersinkronisasi."

        # 4. Susun konteks ke otak AI
        context_str = f"Data Faktual Clan (Tag: {clan_tag}):\n"
        context_str += "--- MEMBER PALING AKTIF (DONASI TERTINGGI) ---\n"
        for m in top_members:
            context_str += f"- {m.name} (TH{m.townhall_level}, Jabatan: {m.role}): Donasi {m.donations}\n"
            
        context_str += "\n--- MEMBER PASIF / TERANCAM KICK (DONASI TERENDAH) ---\n"
        for m in lazy_members:
            context_str += f"- {m.name} (TH{m.townhall_level}, Jabatan: {m.role}): Donasi {m.donations}\n"
            
        return context_str
    except Exception as e:
        logger.error(f"Gagal mengambil konteks DB: {e}")
        return "Gagal memuat data database."
    finally:
        db.close()

async def generate_response(prompt: str, guild_id: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Sistem AI sedang tidak aktif karena API Key tidak ditemukan."
        
    client = genai.Client(api_key=api_key)
    db_context = _get_clan_context_from_db(guild_id)
    
    full_prompt = (
        f"Lu adalah Asisten AI Resmi Clan Clash of Clans (ixiera.id).\n"
        f"Gunakan data faktual di bawah ini untuk menjawab pertanyaan soal kondisi clan, siapa yang aktif, atau siapa yang pasif:\n"
        f"{db_context}\n---------------------\n"
        f"Pertanyaan/Obrolan User: {prompt}"
    )

    try:
        # Panggil API Gemini 3.6 Flash dengan penanganan async
        response = await client.aio.models.generate_content(
            model='gemini-3.6-flash',
            contents=full_prompt
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return "Maaf, koneksi ke AI sedang berhalangan. Coba tanya sekali lagi, bro."
