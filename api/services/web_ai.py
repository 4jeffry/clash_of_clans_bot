import os
import logging
import asyncio
from google import genai

logger = logging.getLogger("api.ai")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

async def generate_narrative(prompt: str) -> str:
    if not GEMINI_KEY:
        return "API Key Gemini belum di-set di Railway."
    
    client = genai.Client(api_key=GEMINI_KEY)
    models_to_try = ['gemini-3.8-flash', 'gemini-3.5-flash-lite']
    
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(model=model_name, contents=prompt)
                return response.text
            except Exception as e:
                if "503" in str(e) or "429" in str(e):
                    await asyncio.sleep(2 ** attempt)
                    continue
                break
    return "Server AI sedang sibuk. Coba lagi nanti."

def get_base_prompt():
    return (
        "Anda adalah Niki, Executive AI System. "
        "Jawaban harus berupa TEKS POLOS, tanpa Markdown, tanpa bintang, tanpa pagar. "
        "Gunakan HURUF KAPITAL untuk judul. Maksimal 2 kalimat per poin. "
        "Gunakan simbol ( - ) untuk list. Langsung berikan laporan intinya."
    )
