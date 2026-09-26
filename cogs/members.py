import discord
from discord import app_commands
from discord.ext import commands
from services.coc_client import CoCClient
from services.db import get_db
from models import ServerConfig

class MemberCommands(commands.Cog):
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

    @app_commands.command(name="donations", description="Melihat Top 5 Donatur di Clan")
    async def top_donations(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup! Gunakan `/setup` terlebih dahulu.")
        
        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data member dari API.")
        
        members = clan_data['memberList']
        top_donators = sorted(members, key=lambda x: x.get('donations', 0), reverse=True)[:5]
        
        embed = discord.Embed(title="🏆 Top 5 Donatur Clan", color=discord.Color.green())
        for i, m in enumerate(top_donators, 1):
            embed.add_field(
                name=f"{i}. {m.get('name')} (TH {m.get('townHallLevel')})", 
                value=f"📤 Donasi: {m.get('donations', 0)} | 📥 Diterima: {m.get('donationsReceived', 0)}", 
                inline=False
            )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="inactive", description="Cek member dengan donasi 0 atau terendah")
    async def check_inactive(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup! Gunakan `/setup` terlebih dahulu.")

        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data dari API.")

        members = clan_data['memberList']
        low_donors = sorted(members, key=lambda x: x.get('donations', 0))[:5]

        embed = discord.Embed(title="⚠️ Member Donasi Terendah / Pasif", color=discord.Color.orange())
        for m in low_donors:
            embed.add_field(
                name=f"{m.get('name')} ({m.get('role').capitalize()})",
                value=f"TH {m.get('townHallLevel')} | Donasi: {m.get('donations', 0)}",
                inline=False
            )
        await interaction.followup.send(embed=embed)

    # BARU: /memberstats [nama]
    @app_commands.command(name="memberstats", description="Melihat detail statistik 1 member clan")
    async def member_stats(self, interaction: discord.Interaction, nama: str):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup! Gunakan `/setup`.")

        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data dari API.")

        target = next((m for m in clan_data['memberList'] if nama.lower() in m.get('name', '').lower()), None)
        if not target:
            return await interaction.followup.send(f"❌ Member dengan nama `{nama}` tidak ditemukan di clan.")

        embed = discord.Embed(title=f"👤 Profil Member: {target.get('name')}", color=discord.Color.blue())
        embed.add_field(name="Tag Player", value=target.get('tag'), inline=True)
        embed.add_field(name="Town Hall", value=f"TH {target.get('townHallLevel')}", inline=True)
        embed.add_field(name="Jabatan", value=target.get('role').capitalize(), inline=True)
        embed.add_field(name="🏆 Trophies", value=f"{target.get('trophies'):,}", inline=True)
        embed.add_field(name="📤 Donasi", value=f"{target.get('donations'):,}", inline=True)
        embed.add_field(name="📥 Diterima", value=f"{target.get('donationsReceived'):,}", inline=True)
        
        await interaction.followup.send(embed=embed)

    # BARU: /compare [m1] [m2]
    @app_commands.command(name="compare", description="Membandingkan performa 2 member clan")
    async def compare_members(self, interaction: discord.Interaction, member1: str, member2: str):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")

        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data.")

        m1 = next((m for m in clan_data['memberList'] if member1.lower() in m.get('name', '').lower()), None)
        m2 = next((m for m in clan_data['memberList'] if member2.lower() in m.get('name', '').lower()), None)

        if not m1 or not m2:
            return await interaction.followup.send("❌ Salah satu atau kedua member tidak ditemukan.")

        embed = discord.Embed(title=f"⚔️ Perbandingan: {m1.get('name')} VS {m2.get('name')}", color=discord.Color.purple())
        embed.add_field(name="Statistik", value="Town Hall\nTrophies\nDonasi\nDonasi Diterima", inline=True)
        embed.add_field(name=m1.get('name'), value=f"TH {m1.get('townHallLevel')}\n🏆 {m1.get('trophies'):,}\n📤 {m1.get('donations'):,}\n📥 {m1.get('donationsReceived'):,}", inline=True)
        embed.add_field(name=m2.get('name'), value=f"TH {m2.get('townHallLevel')}\n🏆 {m2.get('trophies'):,}\n📤 {m2.get('donations'):,}\n📥 {m2.get('donationsReceived'):,}", inline=True)

        await interaction.followup.send(embed=embed)

    # BARU: /leaderboard
    @app_commands.command(name="leaderboard", description="Ranking Trophies tertinggi di clan")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")

        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data.")

        top_trophies = sorted(clan_data['memberList'], key=lambda x: x.get('trophies', 0), reverse=True)[:5]
        embed = discord.Embed(title="🏆 Top 5 Leaderboard Trophies Clan", color=discord.Color.gold())
        for i, m in enumerate(top_trophies, 1):
            embed.add_field(name=f"{i}. {m.get('name')}", value=f"🏆 {m.get('trophies'):,} Trophies | TH {m.get('townHallLevel')}", inline=False)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MemberCommands(bot))
