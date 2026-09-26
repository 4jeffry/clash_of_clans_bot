import discord
from discord import app_commands
from discord.ext import commands
from services.coc_client import CoCClient
from services.db import get_db
from models import ServerConfig

class WarCommands(commands.Cog):
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

    @app_commands.command(name="warstatus", description="Melihat status Clan War saat ini")
    async def warstatus(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")
        
        war_data = await self.coc.get_current_war(clan_tag)
        if not war_data:
            return await interaction.followup.send("🛡️ Clan sedang tidak dalam war atau dalam persiapan awal.")
        
        state = war_data.get('state', 'unknown')
        clan = war_data.get('clan', {})
        opponent = war_data.get('opponent', {})
        
        embed = discord.Embed(title=f"War Status: {state.capitalize()}", color=discord.Color.red())
        embed.add_field(name=clan.get('name', 'Clan Kita'), value=f"⭐ Bintang: {clan.get('stars', 0)}\n🔥 Hancur: {clan.get('destructionPercentage', 0)}%", inline=True)
        embed.add_field(name="VS", value="⚔️", inline=True)
        embed.add_field(name=opponent.get('name', 'Lawan'), value=f"⭐ Bintang: {opponent.get('stars', 0)}\n🔥 Hancur: {opponent.get('destructionPercentage', 0)}%", inline=True)
        
        await interaction.followup.send(embed=embed)

    # BARU: /wartime
    @app_commands.command(name="wartime", description="Cek sisa waktu war & sisa attack yang belum dipakai")
    async def wartime(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")

        war_data = await self.coc.get_current_war(clan_tag)
        if not war_data or war_data.get('state') != 'inWar':
            return await interaction.followup.send("🛡️ Clan sedang tidak dalam masa perang aktif (inWar).")

        clan = war_data.get('clan', {})
        members = clan.get('members', [])
        
        total_attacks_used = sum(len(m.get('attacks', [])) for m in members)
        max_attacks = len(members) * war_data.get('attacksPerMember', 2)
        remaining_attacks = max_attacks - total_attacks_used

        embed = discord.Embed(title="⏰ Wartime & Attack Check", color=discord.Color.dark_red())
        embed.add_field(name="Sisa Attack Clan", value=f"⚔️ **{remaining_attacks}** / {max_attacks} Attack belum dipakai", inline=False)
        embed.add_field(name="Status Perang", value=f"🔥 Destruction: {clan.get('destructionPercentage')}% | ⭐ Stars: {clan.get('stars')}", inline=False)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(WarCommands(bot))
