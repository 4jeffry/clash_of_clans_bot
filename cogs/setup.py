import discord
from discord import app_commands
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

    @app_commands.command(name="setup", description="Mengikat bot ke Clan CoC untuk server ini (Contoh: /setup #2YQUQ...)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_clan(self, interaction: discord.Interaction, clan_tag: str):
        await interaction.response.defer()
        
        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'name' not in clan_data:
            return await interaction.followup.send(f"❌ Tag Clan `{clan_tag}` tidak ditemukan.")

        clan_name = clan_data['name']
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.author.id)

        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == guild_id).first()
            if config:
                config.clan_tag = clan_tag
                config.setup_by = user_id
            else:
                config = ServerConfig(guild_id=guild_id, clan_tag=clan_tag, setup_by=user_id)
                db.add(config)
                
            db.commit()
            
            embed = discord.Embed(title="✅ Setup Berhasil!", description=f"Bot diikat ke Clan **{clan_name}**.", color=discord.Color.green())
            embed.add_field(name="Clan Tag", value=clan_tag, inline=True)
            embed.set_footer(text="Menyinkronkan data ke database AI...")
            
            await interaction.followup.send(embed=embed)
            asyncio.create_task(sync_all_clans())
            
        except Exception as e:
            db.rollback()
            logger.error(f"Gagal menyimpan config server: {e}")
            await interaction.followup.send("❌ Terjadi kesalahan pada database.")
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(SetupCommands(bot))
