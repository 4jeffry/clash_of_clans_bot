import os
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

    @app_commands.command(name="raidstats", description="[FREE] Cek partisipasi & perolehan loot Raid Weekend per member")
    async def raidstats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum terhubung ke clan! Gunakan `/setup`.")

        encoded_tag = urllib.parse.quote(clan_tag)
        data = await self.fetch_coc_api(f"/clans/{encoded_tag}/capitalraidseasons")
        
        if not data or "items" not in data or not data["items"]:
            return await interaction.followup.send("❌ Data Raid Weekend tidak ditemukan.")

        latest_raid = data["items"][0]
        members = latest_raid.get("members", [])
        
        if not members:
            return await interaction.followup.send("ℹ️ Sesi Raid Weekend belum dimulai atau belum ada data partisipan.")

        sorted_participants = sorted(members, key=lambda x: x.get("capitalLoot", 0), reverse=True)[:10]

        table_lines = []
        table_lines.append("#  Nama           Atk  Loot Diperoleh")
        table_lines.append("─────────────────────────────────────")

        for idx, m in enumerate(sorted_participants, 1):
            name = m.get('name', 'Unknown')
            if len(name) > 12:
                name = name[:10] + ".."
            attacks = m.get("attacks", 0)
            max_attacks = m.get("attackLimit", 5) + m.get("bonusAttackLimit", 0)
            loot = m.get("capitalLoot", 0)
            
            table_lines.append(f"{idx:<2} {name:<14} {attacks}/{max_attacks}  {loot:>10,}")

        table_content = "```text\n" + "\n".join(table_lines) + "\n```"

        embed = discord.Embed(
            title="⚔️ TOP 10 PARTISIPAN RAID WEEKEND",
            description="Performa perolehan Capital Gold individual sesi terakhir.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="───────────", value=table_content, inline=False)
        embed.set_footer(text="ixiera.id — Operating System Studio")
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Capital(bot))
