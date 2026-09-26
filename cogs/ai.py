import discord
from discord.ext import commands
from services.llm_client import generate_response

class AICommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if self.bot.user.mentioned_in(message):
            clean_text = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            
            if not clean_text:
                return await message.reply("Ada apa, bro? Mau nanya-nanya soal CoC atau bahas clan?")

            async with message.channel.typing():
                prompt = f"Sebagai asisten AI ahli Clash of Clans. Jawab obrolan ini dengan santai, asik, dan ringkas layaknya teman ngobrol: {clean_text}"
                
                # Kirim guild.id biar AI tahu ini server clan yang mana
                jawaban = await generate_response(prompt, str(message.guild.id))
                
                if len(jawaban) > 2000:
                    jawaban = jawaban[:1997] + "..."
                    
                await message.reply(jawaban)

    @commands.command(name="ask", help="Tanya Gemini tentang strategi CoC, base design, dll.")
    async def ask_ai(self, ctx, *, pertanyaan: str):
        async with ctx.typing():
            prompt = f"Sebagai asisten AI ahli Clash of Clans. Jawab pertanyaan ini dengan ringkas dan jelas: {pertanyaan}"
            
            # Kirim guild.id dari context command
            jawaban = await generate_response(prompt, str(ctx.guild.id))
            
            if len(jawaban) > 2000:
                jawaban = jawaban[:1997] + "..."
                
            await ctx.reply(jawaban)

async def setup(bot):
    await bot.add_cog(AICommands(bot))
