import os
import discord
from discord import app_commands
from discord.ext import commands
from services.coc_client import CoCClient
from services.db import get_db
from models import ServerConfig
from scheduler import sync_all_clans
from datetime import datetime, timedelta
import logging
import asyncio

logger = logging.getLogger('bot.setup')

class SetupCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.coc = CoCClient()

    def _get_owner_id(self):
        # Ambil dari environment Railway, jika tidak ada fallback ke ID kamu
        return os.getenv("MY_DISCORD_ID", "1398954695137038339").strip()

    @app_commands.command(name="setup", description="Mengikat bot ke Clan CoC (Contoh: /setup #2YQUQ...)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_clan(self, interaction: discord.Interaction, clan_tag: str, alert_channel: discord.TextChannel = None):
        await interaction.response.defer()
        
        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'name' not in clan_data:
            return await interaction.followup.send(f"❌ Tag Clan `{clan_tag}` tidak ditemukan.")

        clan_name = clan_data['name']
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        channel_id = str(alert_channel.id) if alert_channel else None

        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == guild_id).first()
            if config:
                config.clan_tag = clan_tag
                config.setup_by = user_id
                if hasattr(config, 'alert_channel_id'):
                    config.alert_channel_id = channel_id
            else:
                config = ServerConfig(guild_id=guild_id, clan_tag=clan_tag, setup_by=user_id)
                if hasattr(config, 'alert_channel_id'):
                    config.alert_channel_id = channel_id
                db.add(config)
                
            db.commit()
            
            embed = discord.Embed(title="✅ Setup Berhasil!", description=f"Bot diikat ke Clan **{clan_name}**.", color=discord.Color.green())
            embed.add_field(name="Clan Tag", value=clan_tag, inline=True)
            if channel_id:
                embed.add_field(name="Alert Channel", value=f"<#{channel_id}>", inline=True)
            embed.set_footer(text="Menyinkronkan data ke database AI...")
            
            await interaction.followup.send(embed=embed)
            asyncio.create_task(sync_all_clans(self.bot))
            
        except Exception as e:
            db.rollback()
            logger.error(f"Gagal menyimpan config server: {e}")
            await interaction.followup.send("❌ Terjadi kesalahan pada database.")
        finally:
            db.close()

    @app_commands.command(name="grant-pro", description="[ADMIN ONLY] Aktifkan lisensi berbayar")
    @app_commands.default_permissions(administrator=True) # Sembunyikan dari user biasa
    async def grant_pro(self, interaction: discord.Interaction, guild_id: str, tier: str, days: int):
        # Verifikasi Owner dari Environment Variable
        if str(interaction.user.id) != self._get_owner_id():
            return await interaction.response.send_message("❌ Command ini khusus Owner Ixiera!", ephemeral=True)

        await interaction.response.defer(ephemeral=True) # Pesan rahasia (ephemeral)
        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == guild_id).first()
            if not config:
                return await interaction.followup.send(f"❌ Server ID `{guild_id}` belum pernah melakukan `/setup`.")

            now = datetime.now()
            base_date = config.expired_at if (config.expired_at and config.expired_at > now) else now
            new_expired = base_date + timedelta(days=days)

            config.tier = tier.lower()
            config.expired_at = new_expired
            db.commit()

            embed = discord.Embed(title="🎉 Lisensi Berhasil Diaktifkan!", color=discord.Color.gold())
            embed.add_field(name="Guild ID", value=guild_id, inline=True)
            embed.add_field(name="Tier Status", value=tier.upper(), inline=True)
            embed.add_field(name="Aktif Sampai", value=new_expired.strftime("%d %B %Y %H:%M"), inline=False)
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            db.rollback()
            await interaction.followup.send("❌ Gagal mengupdate lisensi di database.")
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(SetupCommands(bot))
