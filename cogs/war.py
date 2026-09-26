import discord
from discord.ext import commands
from services.coc_client import CoCClient
from services.db import get_db
from models import ServerConfig

class WarCommands(commands.Cog):
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

    @commands.command(name="warstatus", help="Melihat status Clan War saat ini")
    async def warstatus(self, ctx):
        clan_tag = self.get_clan_tag(ctx.guild.id)
        if not clan_tag:
            return await ctx.send("❌ Server ini belum di-setup! Gunakan `!setup #TAGCLAN` terlebih dahulu.")
        
        msg = await ctx.send("🔄 Mengambil data war dari server...")
        war_data = await self.coc.get_current_war(clan_tag)
        
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