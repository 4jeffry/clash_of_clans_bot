import discord
from discord.ext import commands
from services.coc_client import CoCClient
import os

class MemberCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.coc = CoCClient()
        self.clan_tag = os.getenv('CLAN_TAG')

    @commands.command(name="donations", help="Melihat Top 5 Donatur di Clan")
    async def top_donations(self, ctx):
        if not self.clan_tag:
            return await ctx.send("❌ Setup error: CLAN_TAG belum diatur.")
        
        msg = await ctx.send("🔄 Menganalisis data member...")
        clan_data = await self.coc.get_clan_info(self.clan_tag)
        
        if not clan_data or 'memberList' not in clan_data:
            return await msg.edit(content="❌ Gagal mengambil data member dari API.")
        
        members = clan_data['memberList']
        # Sortir member berdasarkan donasi tertinggi
        top_donators = sorted(members, key=lambda x: x.get('donations', 0), reverse=True)[:5]
        
        embed = discord.Embed(title="🏆 Top 5 Donatur Clan", color=discord.Color.green())
        for i, m in enumerate(top_donators, 1):
            embed.add_field(name=f"{i}. {m.get('name')} (TH {m.get('townHallLevel')})", 
                            value=f"📤 Donasi: {m.get('donations', 0)} | 📥 Diterima: {m.get('donationsReceived', 0)}", 
                            inline=False)
        
        await msg.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(MemberCommands(bot))
