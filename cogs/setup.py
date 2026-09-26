import discord
from discord.ext import commands
from services.coc_client import CoCClient
from services.db import get_db
from models import ServerConfig
from scheduler import sync_all_clans
import logging
import asyncio

logger = logging.getLogger('bot.setup')

class SetupCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.coc = CoCClient()

    @commands.command(name="setup", help="Mengikat bot ke Clan CoC untuk server ini (Contoh: !setup #2YQUQ...)")
    @commands.has_permissions(administrator=True)
    async def setup_clan(self, ctx, clan_tag: str = None):
        if not clan_tag:
            return await ctx.send("❌ Masukkan Tag Clan! Contoh: `!setup #2YQUQ...`")
            
        msg = await ctx.send("🔄 Memvalidasi Tag Clan ke server Clash of Clans...")
        
        clan_data = await self.coc.get_clan_info(clan_tag)
        
        if not clan_data or 'name' not in clan_data:
            return await msg.edit(content=f"❌ Tag Clan `{clan_tag}` tidak ditemukan. Pastikan tag sudah benar!")

        clan_name = clan_data['name']
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == guild_id).first()
            
            if config:
                config.clan_tag = clan_tag
                config.setup_by = user_id
            else:
                config = ServerConfig(
                    guild_id=guild_id,
                    clan_tag=clan_tag,
                    setup_by=user_id
                )
                db.add(config)
                
            db.commit()
            
            embed = discord.Embed(
                title="✅ Setup Berhasil!", 
                description=f"Bot telah diikat ke Clan **{clan_name}**.", 
                color=discord.Color.green()
            )
            embed.add_field(name="Clan Tag", value=clan_tag, inline=True)
            embed.add_field(name="Diatur Oleh", value=ctx.author.mention, inline=True)
            embed.set_footer(text="Menyinkronkan data member ke database AI...")
            
            await msg.edit(content=None, embed=embed)
            logger.info(f"Server {guild_id} setup ke clan {clan_tag} oleh {user_id}")
            
            # TRIGGER SINKRONISASI LANGSUNG
            asyncio.create_task(sync_all_clans())
            
        except Exception as e:
            db.rollback()
            logger.error(f"Gagal menyimpan config server: {e}")
            await msg.edit(content="❌ Terjadi kesalahan pada database saat menyimpan konfigurasi.")
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(SetupCommands(bot))
