import discord
from discord.ext import commands
from services.llm_client import generate_response

class AICommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ask", help="Tanya Gemini tentang strategi CoC, base design, dll.")
    async def ask_ai(self, ctx, *, pertanyaan: str):
        # Menampilkan status 'typing...' di Discord selama Gemini memproses
        async with ctx.typing():
            prompt = f"Sebagai asisten AI ahli Clash of Clans. Jawab pertanyaan ini dengan ringkas dan jelas: {pertanyaan}"
            
            jawaban = await generate_response(prompt)
            
            # Discord memiliki limit 2000 karakter per pesan. Kita potong jika kepanjangan.
            if len(jawaban) > 2000:
                jawaban = jawaban[:1997] + "..."
                
            await ctx.reply(jawaban)

async def setup(bot):
    await bot.add_cog(AICommands(bot))
