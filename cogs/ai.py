import discord
from discord import app_commands
from discord.ext import commands
from services.llm_client import run_ai_audit, run_war_strategy, run_visual_strategy
from services.coc_client import CoCClient
from services.db import get_db
from models import ServerConfig
import asyncio

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.coc = CoCClient()

    def get_clan_tag(self, guild_id):
        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(guild_id)).first()
            return config.clan_tag if config else None
        finally:
            db.close()
            
    async def send_long_message(self, interaction: discord.Interaction, text: str):
        if len(text) <= 2000:
            await interaction.followup.send(text)
        else:
            chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
            for chunk in chunks:
                await interaction.followup.send(chunk)
                await asyncio.sleep(1)

    @app_commands.command(name="ai-audit", description="[AI PRO] Deep audit kesehatan clan & evaluasi member")
    async def ai_audit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        result = await run_ai_audit(str(interaction.guild_id))
        await self.send_long_message(interaction, result)

    @app_commands.command(name="war-strategy", description="[AI PRO] Analisis skor war saat ini & rotasi attack")
    async def ai_war_strategy(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")

        war_data = await self.coc.get_current_war(clan_tag)
        result = await run_war_strategy(str(interaction.guild_id), war_data)
        await self.send_long_message(interaction, result)

    @app_commands.command(name="base-scan", description="[AI PRO] Upload foto base lawan untuk analisis taktik meta")
    async def ai_base_scan(self, interaction: discord.Interaction, foto_base: discord.Attachment):
        await interaction.response.defer()
        if not foto_base.content_type.startswith('image/'):
            return await interaction.followup.send("❌ Tolong upload file berupa gambar (screenshot base).")
            
        image_bytes = await foto_base.read()
        result = await run_visual_strategy(str(interaction.guild_id), image_bytes)
        await self.send_long_message(interaction, result)

async def setup(bot):
    await bot.add_cog(AICog(bot))
