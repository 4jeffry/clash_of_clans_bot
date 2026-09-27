import discord
from discord import app_commands
from discord.ext import commands
import urllib.parse
from services.coc_client import fetch_coc_api  # Pakai helper CoC API client kamu yang sudah ada

class Capital(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="capital", description="[FREE] Ringkasan statistik Clan Capital Raid Weekend terakhir")
    async def capital(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Ambil tag clan dari config server
        # (Sesuaikan dengan helper DB/config kamu, misal ambil dari database)
        from services.db import get_server_config
        config = await get_server_config(str(interaction.guild_id))
        
        if not config or not config.get("clan_tag"):
            await interaction.followup.send("❌ Server ini belum terhubung ke clan CoC! Jalankan `/setup` terlebih dahulu.")
            return

        clan_tag = config["clan_tag"]
        encoded_tag = urllib.parse.quote(clan_tag)
        
        # Call API CoC Raid Seasons
        data = await fetch_coc_api(f"/clans/{encoded_tag}/capitalraidseasons")
        
        if not data or "items" not in data or not data["items"]:
            await interaction.followup.send("❌ Data Clan Capital tidak ditemukan atau tidak ada log Raid Weekend.")
            return

        latest_raid = data["items"][0]
        
        embed = discord.Embed(
            title=f"🏰 Clan Capital Raid Weekend — {clan_tag}",
            color=discord.Color.gold()
        )
        embed.add_field(name="💰 Total Capital Gold", value=f"```{latest_raid.get('capitalTotalLoot', 0):,}```", inline=True)
        embed.add_field(name="⚔️ Total Attacks Used", value=f"```{latest_raid.get('totalAttacks', 0)}```", inline=True)
        embed.add_field(name="💥 Districts Destroyed", value=f"```{latest_raid.get('enemyDistrictsDestroyed', 0)}```", inline=True)
        embed.set_footer(text="Ixiera.id — Operating System Studio")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="capitaldonations", description="[FREE] Top 5 donatur Capital Gold di clan")
    async def capitaldonations(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        from services.db import get_server_config
        config = await get_server_config(str(interaction.guild_id))
        
        if not config or not config.get("clan_tag"):
            await interaction.followup.send("❌ Server belum terhubung ke clan! Gunakan `/setup`.")
            return

        clan_tag = config["clan_tag"]
        encoded_tag = urllib.parse.quote(clan_tag)
        
        clan_data = await fetch_coc_api(f"/clans/{encoded_tag}")
        if not clan_data or "memberList" not in clan_data:
            await interaction.followup.send("❌ Gagal mengambil data member clan.")
            return

        # Urutkan berdasarkan kontribusi Capital Gold terbanyak
        members = clan_data["memberList"]
        sorted_members = sorted(members, key=lambda x: x.get("clanCapitalContributions", 0), reverse=True)[:5]

        description = ""
        for idx, m in enumerate(sorted_members, 1):
            gold = m.get("clanCapitalContributions", 0)
            description += f"**{idx}. {m['name']}** — 💰 `{gold:,}` Capital Gold\n"

        embed = discord.Embed(
            title=f"🏛️ Top 5 Donatur Clan Capital — {clan_data['name']}",
            description=description or "Belum ada data donasi.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Ixiera.id — Operating System Studio")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="raidstats", description="[FREE] Cek penggunaan serangan Raid Weekend per member")
    async def raidstats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        from services.db import get_server_config
        config = await get_server_config(str(interaction.guild_id))
        
        if not config or not config.get("clan_tag"):
            await interaction.followup.send("❌ Server belum terhubung ke clan! Gunakan `/setup`.")
            return

        clan_tag = config["clan_tag"]
        encoded_tag = urllib.parse.quote(clan_tag)
        
        data = await fetch_coc_api(f"/clans/{encoded_tag}/capitalraidseasons")
        if not data or "items" not in data or not data["items"]:
            await interaction.followup.send("❌ Data Raid Weekend tidak ditemukan.")
            return

        latest_raid = data["items"][0]
        members = latest_raid.get("members", [])
        
        if not members:
            await interaction.followup.send("ℹ️ Sesi Raid Weekend belum dimulai atau belum ada partisipan.")
            return

        # Urutkan berdasarkan loot terbanyak
        sorted_participants = sorted(members, key=lambda x: x.get("capitalLoot", 0), reverse=True)[:10]

        desc = ""
        for idx, m in enumerate(sorted_participants, 1):
            attacks = m.get("attacks", 0)
            max_attacks = m.get("attackLimit", 5) + m.get("bonusAttackLimit", 0)
            loot = m.get("capitalLoot", 0)
            desc += f"**{idx}. {m['name']}** — ⚔️ `{attacks}/{max_attacks}` attacks | 💰 `{loot:,}` loot\n"

        embed = discord.Embed(
            title="⚔️ Top 10 Partisipan Raid Weekend Sesi Ini",
            description=desc,
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Ixiera.id — Operating System Studio")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Capital(bot))
