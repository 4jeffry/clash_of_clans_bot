import discord
from discord import app_commands
from discord.ext import commands
from services.llm_client import (
    run_ai_audit, 
    run_war_strategy, 
    run_visual_strategy, 
    run_ai_screen, 
    run_ai_scout
)
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

    @app_commands.command(name="base-scan", description="[AI PRO] Upload foto base lawan & opsional ketik combo/equipment")
    async def ai_base_scan(
        self, 
        interaction: discord.Interaction, 
        foto_base: discord.Attachment,
        detail_pasukan: str = None
    ):
        await interaction.response.defer()
        if not foto_base.content_type.startswith('image/'):
            return await interaction.followup.send("❌ Tolong upload file berupa gambar (screenshot base).")
            
        image_bytes = await foto_base.read()
        result = await run_visual_strategy(str(interaction.guild_id), image_bytes, detail_pasukan)
        await self.send_long_message(interaction, result)

    @app_commands.command(name="ai-screen", description="[AI PRO] Cek profil calon member sebelum di-acc join")
    @app_commands.describe(player_tag="Tag player calon member (contoh: #ABC1234)")
    async def ai_screen(self, interaction: discord.Interaction, player_tag: str):
        await interaction.response.defer()
        
        if not player_tag.startswith('#'):
            player_tag = f"#{player_tag}"
            
        player_data = await self.coc.get_player_info(player_tag)
        if not player_data or 'tag' not in player_data:
            return await interaction.followup.send("❌ Data player tidak ditemukan! Pastikan tag-nya benar.")

        result = await run_ai_screen(str(interaction.guild_id), player_data)
        await self.send_long_message(interaction, result)

    @app_commands.command(name="ai-scout", description="[AI PRO] Intel war lawan: cari base terlemah & strategi perakitan bintang")
    async def ai_scout(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")

        war_data = await self.coc.get_current_war(clan_tag)
        if not war_data or war_data.get('state') not in ['inWar', 'preparation']:
            return await interaction.followup.send("❌ Clan sedang tidak dalam periode War aktif!")

        result = await run_ai_scout(str(interaction.guild_id), war_data)
        await self.send_long_message(interaction, result)

async def setup(bot):
    await bot.add_cog(AICog(bot))
