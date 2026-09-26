import discord
from discord import app_commands
from discord.ext import commands
from services.coc_client import CoCClient
from services.db import get_db
from models import ServerConfig
from collections import Counter

class ClanCommands(commands.Cog):
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

    # BARU: /clanmembers
    @app_commands.command(name="clanmembers", description="Melihat daftar semua member clan beserta jabatannya")
    async def clan_members(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")

        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data.")

        members = clan_data['memberList']
        embed = discord.Embed(title=f"📋 Daftar Member {clan_data.get('name')} ({len(members)}/50)", color=discord.Color.dark_blue())

        # Grouping ringkas
        leaders = [m.get('name') for m in members if m.get('role') in ['leader', 'coLeader']]
        elders = [m.get('name') for m in members if m.get('role') == 'admin']
        
        embed.add_field(name="👑 Leader & Co-Leader", value=", ".join(leaders) if leaders else "-", inline=False)
        embed.add_field(name="🛡️ Elder", value=", ".join(elders) if elders else "-", inline=False)
        embed.add_field(name="⚔️ Total Member", value=f"Gunakan `/memberstats [nama]` untuk cek detail player.", inline=False)

        await interaction.followup.send(embed=embed)

    # BARU: /thcomposition
    @app_commands.command(name="thcomposition", description="Melihat breakdown komposisi level Town Hall di clan")
    async def th_composition(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")

        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data.")

        th_levels = [m.get('townHallLevel') for m in clan_data['memberList']]
        th_counts = Counter(th_levels)

        embed = discord.Embed(title=f"🏛️ Komposisi Town Hall {clan_data.get('name')}", color=discord.Color.teal())
        
        # Urutkan dari TH tertinggi ke terendah
        for th in sorted(th_counts.keys(), reverse=True):
            count = th_counts[th]
            embed.add_field(name=f"TH {th}", value=f"👥 **{count}** Member", inline=True)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ClanCommands(bot))
