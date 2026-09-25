import os
import google.generativeai as genai
import logging

logger = logging.getLogger('bot.llm')

def setup_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY tidak ditemukan di .env!")
        return None
        
    genai.configure(api_key=api_key)
    # Menggunakan model sesuai instruksi
    return genai.GenerativeModel('gemini-3.6-flash')

model = setup_gemini()

async def generate_response(prompt: str) -> str:
    if not model:
        return "Sistem AI sedang tidak aktif karena API Key tidak ditemukan."
        
    try:
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return "Maaf, terjadi kesalahan saat memproses permintaan ke AI."
