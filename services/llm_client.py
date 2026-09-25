import os
import google.generativeai as genai
import logging
from services.db import get_db
from models import ClanMember

logger = logging.getLogger('bot.llm')

def setup_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY tidak ditemukan di .env!")
        return None
        
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-flash')

model = setup_gemini()

def _get_clan_context_from_db() -> str:
    """Mengambil snapshot data asli dari database Supabase sebagai referensi AI"""
    db = get_db()
    try:
        members = db.query(ClanMember).order_by(ClanMember.donations.desc()).limit(10).all()
        if not members:
            return "Data database kosong."

        context_str = "Data Riwayat Clan Saat Ini (Real-time dari Database):\n"
        for m in members:
            context_str += f"- {m.name} (TH{m.townhall_level}, Jabatan: {m.role}): Donasi {m.donations}, Diterima {m.donations_received}\n"
        return context_str
    except Exception as e:
        logger.error(f"Gagal mengambil konteks DB untuk LLM: {e}")
        return "Gagal memuat data database."
    finally:
        db.close()

async def generate_response(prompt: str) -> str:
    if not model:
        return "Sistem AI sedang tidak aktif karena API Key tidak ditemukan."
        
    db_context = _get_clan_context_from_db()
    
    # Gabungkan konteks asli database ke sistem prompt
    full_prompt = (
        f"Lu adalah Asisten AI Resmi Clan Clash of Clans (ixiera.id).\n"
        f"Gunakan data faktual dari database di bawah ini untuk menjawab jika pertanyaan berhubungan dengan member/donasi:\n"
        f"--- DATA DATABASE ---\n{db_context}\n---------------------\n"
        f"Pertanyaan User: {prompt}"
    )

    try:
        response = await model.generate_content_async(full_prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return "Maaf, terjadi kesalahan saat memproses permintaan ke AI."
