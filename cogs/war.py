import discord
from discord.ext import commands
from services.coc_client import CoCClient
import os

class WarCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.coc = CoCClient()
        self.clan_tag = os.getenv('CLAN_TAG')

    @commands.command(name="warstatus", help="Melihat status Clan War saat ini")
    async def warstatus(self, ctx):
        if not self.clan_tag:
            return await ctx.send("❌ Setup error: CLAN_TAG belum diatur.")
        
        msg = await ctx.send("🔄 Mengambil data war dari server...")
        war_data = await self.coc.get_current_war(self.clan_tag)
        
        if not war_data:
            return await msg.edit(content="🛡️ Clan sedang tidak dalam war atau sedang masa persiapan awal.")
        
        state = war_data.get('state', 'unknown')
        clan = war_data.get('clan', {})
        opponent = war_data.get('opponent', {})
        
        embed = discord.Embed(title=f"War Status: {state.capitalize()}", color=discord.Color.red())
        embed.add_field(name=clan.get('name', 'Clan Kita'), 
                        value=f"⭐ Bintang: {clan.get('stars', 0)}\n🔥 Hancur: {clan.get('destructionPercentage', 0)}%", 
                        inline=True)
        embed.add_field(name="VS", value="⚔️", inline=True)
        embed.add_field(name=opponent.get('name', 'Lawan'), 
                        value=f"⭐ Bintang: {opponent.get('stars', 0)}\n🔥 Hancur: {opponent.get('destructionPercentage', 0)}%", 
                        inline=True)
        
        await msg.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(WarCommands(bot))
