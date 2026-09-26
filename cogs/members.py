import discord
from discord.ext import commands
from services.coc_client import CoCClient
from services.db import get_db
from models import ClanMember, ServerConfig

class MemberCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.coc = CoCClient()

    def get_clan_tag(self, guild_id):
        """Fungsi pembantu untuk mengambil Tag Clan dari database berdasarkan Server Discord"""
        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(guild_id)).first()
            return config.clan_tag if config else None
        finally:
            db.close()

    @commands.command(name="donations", help="Melihat Top 5 Donatur di Clan")
    async def top_donations(self, ctx):
        clan_tag = self.get_clan_tag(ctx.guild.id)
        if not clan_tag:
            return await ctx.send("❌ Server ini belum di-setup! Gunakan `!setup #TAGCLAN` terlebih dahulu.")
        
        msg = await ctx.send("🔄 Menganalisis data member...")
        clan_data = await self.coc.get_clan_info(clan_tag)
        
        if not clan_data or 'memberList' not in clan_data:
            return await msg.edit(content="❌ Gagal mengambil data member dari API.")
        
        members = clan_data['memberList']
        top_donators = sorted(members, key=lambda x: x.get('donations', 0), reverse=True)[:5]
        
        embed = discord.Embed(title="🏆 Top 5 Donatur Clan", color=discord.Color.green())
        for i, m in enumerate(top_donators, 1):
            embed.add_field(
                name=f"{i}. {m.get('name')} (TH {m.get('townHallLevel')})", 
                value=f"📤 Donasi: {m.get('donations', 0)} | 📥 Diterima: {m.get('donationsReceived', 0)}", 
                inline=False
            )
        
        await msg.edit(content=None, embed=embed)

    @commands.command(name="inactive", help="Cek member dengan donasi 0 atau terendah")
    async def check_inactive(self, ctx):
        clan_tag = self.get_clan_tag(ctx.guild.id)
        if not clan_tag:
            return await ctx.send("❌ Server ini belum di-setup! Gunakan `!setup #TAGCLAN` terlebih dahulu.")

        msg = await ctx.send("🔍 Mengidentifikasi member pasif...")
        clan_data = await self.coc.get_clan_info(clan_tag)
        
        if not clan_data or 'memberList' not in clan_data:
            return await msg.edit(content="❌ Gagal mengambil data dari API.")

        members = clan_data['memberList']
        low_donors = sorted(members, key=lambda x: x.get('donations', 0))[:5]

        embed = discord.Embed(title="⚠️ Member Donasi Terendah / Pasif", color=discord.Color.orange())
        for m in low_donors:
            embed.add_field(
                name=f"{m.get('name')} ({m.get('role').capitalize()})",
                value=f"TH {m.get('townHallLevel')} | Donasi: {m.get('donations', 0)}",
                inline=False
            )

        await msg.edit(content=None, embed=embed)

    @commands.command(name="clanstats", help="Statistik ringkas komposisi clan")
    async def clan_stats(self, ctx):
        clan_tag = self.get_clan_tag(ctx.guild.id)
        if not clan_tag:
            return await ctx.send("❌ Server ini belum di-setup! Gunakan `!setup #TAGCLAN` terlebih dahulu.")

        msg = await ctx.send("📊 Mengalkulasi statistik clan...")
        clan_data = await self.coc.get_clan_info(clan_tag)
        
        if not clan_data or 'memberList' not in clan_data:
            return await msg.edit(content="❌ Gagal mengambil data.")

        members = clan_data['memberList']
        total_members = len(members)
        total_donations = sum(m.get('donations', 0) for m in members)
        avg_th = sum(m.get('townHallLevel', 0) for m in members) / total_members if total_members > 0 else 0

        embed = discord.Embed(title=f"📈 Ringkasan Statistik {clan_data.get('name')}", color=discord.Color.blue())
        embed.add_field(name="👥 Total Member", value=f"{total_members}/50", inline=True)
        embed.add_field(name="🛡️ Rata-rata TH", value=f"TH {avg_th:.1f}", inline=True)
        embed.add_field(name="🎁 Total Donasi Clan", value=f"{total_donations:,}", inline=False)

        await msg.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(MemberCommands(bot))