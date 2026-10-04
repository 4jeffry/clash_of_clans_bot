import discord
from discord import app_commands
from discord.ext import commands
import csv
import io
from services.coc_client import CoCClient
from services.db import get_db, check_standar_access
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

    @app_commands.command(name="donations", description="Melihat Top Donatur & Unduh CSV Rekap Full Member")
    async def top_donations(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup! Gunakan `/setup` terlebih dahulu.")
        
        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data member dari API.")
        
        members = clan_data['memberList']
        # Urutkan seluruh member berdasarkan donasi tertinggi
        sorted_members = sorted(members, key=lambda x: x.get('donations', 0), reverse=True)
        top_donators = sorted_members[:5]
        
        # Format Tabel Clean (Monospace)
        table_lines = []
        table_lines.append("#  Nama           TH   Donasi  Rasio")
        table_lines.append("────────────────────────────────────")
        
        for rank, m in enumerate(top_donators, 1):
            name = m.get('name', 'Unknown')
            # Potong nama jika lebih dari 12 karakter agar tabel tetap simetris di HP
            if len(name) > 12:
                name = name[:10] + ".."
                
            th = m.get('townHallLevel', 0)
            don = m.get('donations', 0)
            rec = m.get('donationsReceived', 0)
            ratio = round(don / rec, 2) if rec > 0 else (don if don > 0 else 0)
            
            # Formatting rata kolom: # (2) | Nama (14) | TH (4) | Donasi (8) | Rasio (6)
            line = f"{rank:<2} {name:<14} {th:<4} {don:>6,}  {ratio:>5}"
            table_lines.append(line)
            
        table_content = "```text\n" + "\n".join(table_lines) + "\n```"

        embed = discord.Embed(
            title=f"🏆 TOP 5 DONATUR CLAN",
            description=f"**{clan_data.get('name', 'Clan')}** • Musim Aktif\n*Rekap donasi seluruh anggota terlampir dalam file CSV.*",
            color=discord.Color.gold()
        )
        embed.add_field(name="───────────", value=table_content, inline=False)

        # Generate CSV in-memory
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["Rank", "Nama", "Tag", "Role", "TH", "Donasi", "Diterima", "Rasio"])
        
        for rank, m in enumerate(sorted_members, 1):
            don = m.get('donations', 0)
            rec = m.get('donationsReceived', 0)
            ratio = round(don / rec, 2) if rec > 0 else (don if don > 0 else 0)
            writer.writerow([rank, m.get('name'), m.get('tag'), m.get('role').capitalize(), m.get('townHallLevel'), don, rec, ratio])
            
        csv_buffer.seek(0)
        csv_file = discord.File(fp=io.BytesIO(csv_buffer.getvalue().encode('utf-8')), filename=f"Rekap_Donasi_{clan_tag.replace('#', '')}.csv")

        # Kirim Embed & File CSV
        await interaction.followup.send(embed=embed, file=csv_file)

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

        table_lines = []
        table_lines.append("#  Nama           TH   Role       Donasi")
        table_lines.append("────────────────────────────────────────")
        
        for rank, m in enumerate(low_donors, 1):
            name = m.get('name', 'Unknown')
            if len(name) > 12:
                name = name[:10] + ".."
            th = m.get('townHallLevel', 0)
            role = m.get('role', 'member').capitalize()
            don = m.get('donations', 0)
            
            line = f"{rank:<2} {name:<14} {th:<4} {role:<10} {don:>6,}"
            table_lines.append(line)

        table_content = "```text\n" + "\n".join(table_lines) + "\n```"

        embed = discord.Embed(title="⚠️ MEMBER DONASI TERENDAH / PASIF", color=discord.Color.orange())
        embed.add_field(name="───────────", value=table_content, inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="memberstats", description="Melihat detail statistik 1 member clan")
    async def member_stats(self, interaction: discord.Interaction, nama: str):
        await interaction.response.defer()
        
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg)

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
        embed.add_field(name="Tag Player", value=f"`{target.get('tag')}`", inline=True)
        embed.add_field(name="Town Hall", value=f"`TH {target.get('townHallLevel')}`", inline=True)
        embed.add_field(name="Jabatan", value=f"`{target.get('role').capitalize()}`", inline=True)
        embed.add_field(name="🏆 Trophies", value=f"`{target.get('trophies'):,}`", inline=True)
        embed.add_field(name="📤 Donasi", value=f"`{target.get('donations'):,}`", inline=True)
        embed.add_field(name="📥 Diterima", value=f"`{target.get('donationsReceived'):,}`", inline=True)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="compare", description="Membandingkan performa 2 member clan")
    async def compare_members(self, interaction: discord.Interaction, member1: str, member2: str):
        await interaction.response.defer()
        
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg)

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

        embed = discord.Embed(title=f"⚔️ Perbandingan Member", color=discord.Color.purple())
        embed.add_field(name="Statistik", value="```text\nTown Hall\nTrophies\nDonasi\nDiterima\n```", inline=True)
        embed.add_field(name=m1.get('name')[:12], value=f"```text\nTH {m1.get('townHallLevel')}\n{m1.get('trophies'):,}\n{m1.get('donations'):,}\n{m1.get('donationsReceived'):,}\n```", inline=True)
        embed.add_field(name=m2.get('name')[:12], value=f"```text\nTH {m2.get('townHallLevel')}\n{m2.get('trophies'):,}\n{m2.get('donations'):,}\n{m2.get('donationsReceived'):,}\n```", inline=True)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="leaderboard", description="Ranking Trophies tertinggi di clan")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")

        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data.")

        top_trophies = sorted(clan_data['memberList'], key=lambda x: x.get('trophies', 0), reverse=True)[:5]
        
        table_lines = []
        table_lines.append("#  Nama           TH   Trophies")
        table_lines.append("──────────────────────────────────")
        
        for rank, m in enumerate(top_trophies, 1):
            name = m.get('name', 'Unknown')
            if len(name) > 12:
                name = name[:10] + ".."
            th = m.get('townHallLevel', 0)
            trophies = m.get('trophies', 0)
            
            line = f"{rank:<2} {name:<14} {th:<4} {trophies:>8,}"
            table_lines.append(line)

        table_content = "```text\n" + "\n".join(table_lines) + "\n```"

        embed = discord.Embed(title="🏆 TOP 5 LEADERBOARD TROPHIES", color=discord.Color.gold())
        embed.add_field(name="───────────", value=table_content, inline=False)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MemberCommands(bot))
