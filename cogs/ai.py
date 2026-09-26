import discord
from discord import app_commands
from discord.ext import commands
from services.llm_client import run_ai_audit, run_war_strategy
from services.coc_client import CoCClient
from services.db import get_db
from models import ServerConfig

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

    @app_commands.command(name="ai-audit", description="[AI PRO] Deep audit kesehatan clan & rekomendasi evaluasi member")
    async def ai_audit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        result = await run_ai_audit(str(interaction.guild_id))
        await interaction.followup.send(result)

    @app_commands.command(name="war-strategy", description="[AI PRO] Analisis taktik & rekomendasi pemetaan serangan war")
    async def ai_war_strategy(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup! Gunakan `/setup` terlebih dahulu.")

        war_data = await self.coc.get_current_war(clan_tag)
        result = await run_war_strategy(str(interaction.guild_id), war_data)
        await interaction.followup.send(result)

async def setup(bot):
    await bot.add_cog(AICog(bot))
