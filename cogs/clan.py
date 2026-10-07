import discord
from discord import app_commands
from discord.ext import commands
from services.coc_client import CoCClient
from services.db import get_db, check_standar_access
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

    @app_commands.command(name="clanmembers", description="Melihat demografi TH dan roster struktur jabatan clan")
    async def clan_members(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")

        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data dari API.")

        members = clan_data['memberList']
        
        # 1. Hitung Demografi TH
        th_levels = [m.get('townHallLevel') for m in members]
        th_counts = Counter(th_levels)
        
        # Format teks Demografi (contoh: TH 16: 5 | TH 15: 12)
        th_lines = []
        for th in sorted(th_counts.keys(), reverse=True):
            th_lines.append(f"TH {th}: {th_counts[th]}")
        th_text = " | ".join(th_lines)

        # 2. Fungsi Pembantu untuk Memformat Roster + Tag TH
        def format_roster(role_list):
            role_members = [m for m in members if m.get('role') in role_list]
            return ", ".join([f"{m.get('name')} (TH{m.get('townHallLevel')})" for m in role_members])

        leaders_text = format_roster(['leader', 'coLeader'])
        elders_text = format_roster(['admin'])
        
        embed = discord.Embed(
            title=f"📊 DEMOGRAFI & ROSTER: {clan_data.get('name')}", 
            description=f"Total: **{len(members)}/50 Member**\n*Gunakan `/memberstats [nama]` untuk cek detail individu.*", 
            color=discord.Color.dark_blue()
        )
        
        embed.add_field(name="🔰 Kekuatan Town Hall", value=f"```text\n{th_text}\n```", inline=False)
        
        if leaders_text:
            embed.add_field(name="👑 Leader & Co-Leader", value=leaders_text, inline=False)
        if elders_text:
            # Batasi string agar tidak melebihi limit 1024 karakter Discord embed field
            if len(elders_text) > 1000:
                elders_text = elders_text[:1000] + "..."
            embed.add_field(name="🛡️ Elder", value=elders_text, inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="thcomposition", description="Melihat breakdown komposisi level Town Hall di clan")
    async def th_composition(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # 🔒 LOCK GUARD FOR TIER STANDAR
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")

        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data.")

        th_levels = [m.get('townHallLevel') for m in clan_data['memberList']]
        th_counts = Counter(th_levels)

        embed = discord.Embed(title=f"🏛️ Komposisi Town Hall {clan_data.get('name')}", color=discord.Color.teal())
        
        for th in sorted(th_counts.keys(), reverse=True):
            count = th_counts[th]
            embed.add_field(name=f"TH {th}", value=f"👥 **{count}** Member", inline=True)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ClanCommands(bot))
