import os
import io
import csv
import discord
import aiohttp
import urllib.parse
from discord import app_commands
from discord.ext import commands

from services.db import get_db
from models import ServerConfig

class Capital(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_coc_api(self, endpoint):
        token = os.getenv('COC_API_TOKEN')
        url = f"https://cocproxy.royaleapi.dev/v1{endpoint}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None

    def get_clan_tag(self, guild_id):
        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(guild_id)).first()
            if config:
                return config.clan_tag
            return None
        finally:
            db.close()

    @app_commands.command(name="capital", description="[FREE] Ringkasan statistik Clan Capital Raid Weekend terakhir")
    async def capital(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum terhubung ke clan CoC! Jalankan `/setup` terlebih dahulu.")

        encoded_tag = urllib.parse.quote(clan_tag)
        data = await self.fetch_coc_api(f"/clans/{encoded_tag}/capitalraidseasons")
        
        if not data or "items" not in data or not data["items"]:
            return await interaction.followup.send("❌ Data Clan Capital tidak ditemukan atau log Raid Weekend belum tersedia.")

        latest_raid = data["items"][0]
        total_loot = latest_raid.get('capitalTotalLoot', 0)
        total_attacks = latest_raid.get('totalAttacks', 0)
        districts_destroyed = latest_raid.get('enemyDistrictsDestroyed', 0)
        defensive_rewards = latest_raid.get('defensiveReward', 0)
        completed_raids = latest_raid.get('raidsCompleted', 0)

        box_content = (
            f"```text\n"
            f"💰 Total Loot       : {total_loot:,} Gold\n"
            f"⚔️ Total Attack     : {total_attacks} Serangan\n"
            f"💥 Distrik Rata     : {districts_destroyed}\n"
            f"🏆 Raid Selesai     : {completed_raids}\n"
            f"🛡️ Bonus Pertahanan : {defensive_rewards:,} Gold\n"
            f"```"
        )

        embed = discord.Embed(
            title=f"🏰 CLAN CAPITAL RAID WEEKEND",
            description=f"Ringkasan performa distrik klan pada sesi terakhir.",
            color=discord.Color.gold()
        )
        embed.add_field(name="───────────", value=box_content, inline=False)
        embed.set_footer(text="ixiera.id — Operating System Studio")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="capitaldonations", description="[FREE] Top 10 donatur kontribusi Capital Gold di clan")
    async def capitaldonations(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum terhubung ke clan! Gunakan `/setup`.")

        encoded_tag = urllib.parse.quote(clan_tag)
        clan_data = await self.fetch_coc_api(f"/clans/{encoded_tag}")
        
        if not clan_data or "memberList" not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data member clan dari API.")

        members = clan_data["memberList"]
        sorted_members = sorted(members, key=lambda x: x.get("clanCapitalContributions", 0), reverse=True)[:10]

        table_lines = []
        table_lines.append("#  Nama           TH   Kontribusi Gold")
        table_lines.append("───────────────────────────────────────")
        
        for idx, m in enumerate(sorted_members, 1):
            name = m.get('name', 'Unknown')
            if len(name) > 12:
                name = name[:10] + ".."
            th = m.get('townHallLevel', 0)
            gold = m.get("clanCapitalContributions", 0)
            
            table_lines.append(f"{idx:<2} {name:<14} {th:<4} {gold:>10,}")

        table_content = "```text\n" + "\n".join(table_lines) + "\n```"

        embed = discord.Embed(
            title=f"🏛️ TOP 10 DONATUR CAPITAL GOLD",
            description=f"**{clan_data.get('name', 'Clan')}** • Akumulasi Kontribusi Total",
            color=discord.Color.green()
        )
        embed.add_field(name="───────────", value=table_content, inline=False)
        embed.set_footer(text="ixiera.id — Operating System Studio")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="raidstats", description="[FREE] Cek Top 10 partisipan Raid & Unduh CSV Rekap Full Member")
    async def raidstats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum terhubung ke clan! Gunakan `/setup`.")

        encoded_tag = urllib.parse.quote(clan_tag)
        
        clan_info = await self.fetch_coc_api(f"/clans/{encoded_tag}")
        if not clan_info or 'memberList' not in clan_info:
            return await interaction.followup.send("❌ Gagal mengambil data clan.")
        
        all_members = {m['tag']: m['name'] for m in clan_info['memberList']}
        clan_name = clan_info.get('name', 'Clan')

        raid_data = await self.fetch_coc_api(f"/clans/{encoded_tag}/capitalraidseasons")
        if not raid_data or "items" not in raid_data or not raid_data["items"]:
            return await interaction.followup.send("❌ Data Raid Weekend tidak ditemukan.")

        latest_raid = raid_data["items"][0]
        raid_members = {m['tag']: m for m in latest_raid.get("members", [])}
        
        csv_data = []
        csv_data.append(["Nama Member", "Status Raid", "Serangan Terpakai", "Maksimal Serangan", "Sisa Serangan", "Loot Diperoleh"])
        
        for tag, name in all_members.items():
            if tag not in raid_members:
                csv_data.append([name, "Belum Attack", 0, 5, 5, 0])
            else:
                rm = raid_members[tag]
                attacks = rm.get("attacks", 0)
                max_attacks = rm.get("attackLimit", 5) + rm.get("bonusAttackLimit", 0)
                sisa_attacks = max_attacks - attacks
                loot = rm.get("capitalResourcesLooted", 0)

                if attacks == 0:
                    status = "Belum Attack"
                elif attacks < max_attacks:
                    status = "Sudah Attack"
                else:
                    status = "Max Attack"
                    
                csv_data.append([name, status, attacks, max_attacks, sisa_attacks, loot])

        status_order = {"Belum Attack": 1, "Sudah Attack": 2, "Max Attack": 3}
        sorted_rows = sorted(csv_data[1:], key=lambda x: (status_order[x[1]], -x[5]))
        
        final_csv_data = [csv_data[0]] + sorted_rows

        final_csv_data.append([])
        final_csv_data.append(["*CATATAN SISTEM:"])
        final_csv_data.append(["1. Jatah serangan awal setiap member adalah 5."])
        final_csv_data.append(["2. Member mendapat bonus +1 serangan (Maksimal 6) jika berhasil meratakan 1 distrik lawan."])
        final_csv_data.append(["3. Member yang 'Belum Attack' akan selalu tertulis maksimal serangannya 5 karena belum memicu bonus."])

        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerows(final_csv_data)
        
        file_bytes = io.BytesIO(csv_buffer.getvalue().encode('utf-8-sig'))
        filename = f"Raid_Rekap_{clan_name.replace(' ', '_')}.csv"
        discord_file = discord.File(fp=file_bytes, filename=filename)

        sorted_participants = sorted(latest_raid.get("members", []), key=lambda x: x.get("capitalResourcesLooted", 0), reverse=True)[:10]

        table_lines = []
        table_lines.append("#  Nama           Atk  Loot")
        table_lines.append("────────────────────────────────")

        for idx, m in enumerate(sorted_participants, 1):
            name = m.get('name', 'Unknown')
            if len(name) > 12:
                name = name[:10] + ".."
            attacks = m.get("attacks", 0)
            max_attacks = m.get("attackLimit", 5) + m.get("bonusAttackLimit", 0)
            loot = m.get("capitalResourcesLooted", 0)
            
            table_lines.append(f"{idx:<2} {name:<14} {attacks}/{max_attacks}  {loot:>6,}")

        table_content = "```text\n" + "\n".join(table_lines) + "\n```"

        embed = discord.Embed(
            title=f"⚔️ TOP 10 RAID WEEKEND",
            description=(
                f"**{clan_name}** • Perolehan loot sesi terakhir.\n\n"
                f"Unduh file **CSV** di bawah untuk merekap detail status sisa serangan seluruh member.\n\n"
                f"📌 **Info CoC:** *Jatah awal serangan adalah 5. Member mendapat bonus +1 (Max 6) jika meratakan distrik.*"
            ),
            color=discord.Color.blurple()
        )
        embed.add_field(name="───────────", value=table_content, inline=False)
        embed.set_footer(text="ixiera.id — Operating System Studio")
        
        await interaction.followup.send(embed=embed, file=discord_file)

async def setup(bot):
    await bot.add_cog(Capital(bot))
