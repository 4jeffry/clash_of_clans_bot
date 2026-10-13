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
        return os.getenv("MY_DISCORD_ID", "1398954695137038339").strip()

    @app_commands.command(name="setup", description="Mengikat bot ke Clan CoC (Contoh: /setup #2YQUQ...)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_clan(self, interaction: discord.Interaction, clan_tag: str, alert_channel: discord.TextChannel = None):
        await interaction.response.defer()
        
        clan_tag = clan_tag.strip().upper()
        if not clan_tag.startswith("#"):
            clan_tag = f"#{clan_tag}"

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
    @app_commands.default_permissions(administrator=True)
    async def grant_pro(self, interaction: discord.Interaction, guild_id: str, tier: str, days: int):
        if str(interaction.user.id) != self._get_owner_id():
            return await interaction.response.send_message("❌ Command ini khusus Owner Ixiera!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
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

    @app_commands.command(name="broadcast-promo", description="[OWNER ONLY] Broadcast pesan promo ke server free yang belum pernah trial")
    @app_commands.describe(promo_text="Teks isi pengumuman atau promo yang ingin dikirim")
    async def broadcast_promo(self, interaction: discord.Interaction, promo_text: str):
        if str(interaction.user.id) != self._get_owner_id():
            return await interaction.response.send_message("❌ Command ini khusus Owner Ixiera!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        
        db = get_db()
        try:
            eligible_configs = db.query(ServerConfig).filter(
                ServerConfig.tier.ilike('free'),
                ServerConfig.expired_at == None
            ).all()
            
            eligible_guild_ids = [config.guild_id for config in eligible_configs]
        finally:
            db.close()

        if not eligible_guild_ids:
            return await interaction.followup.send("❌ Tidak ada server free yang memenuhi syarat (semua sudah pernah trial/pro).")

        success_count = 0
        failed_count = 0

        for guild_id_str in eligible_guild_ids:
            guild = self.bot.get_guild(int(guild_id_str))
            if not guild:
                continue

            target_channel = guild.system_channel
            if not target_channel or not target_channel.permissions_for(guild.me).send_messages:
                target_channel = next((channel for channel in guild.text_channels if channel.permissions_for(guild.me).send_messages), None)

            if target_channel:
                try:
                    embed = discord.Embed(
                        title="🎁 Penawaran Spesial Niki System!",
                        description=promo_text,
                        color=discord.Color.brand_green()
                    )
                    embed.set_footer(text="ixiera.id — Operating System Studio | Abaikan pesan ini jika tidak berminat.")
                    
                    await target_channel.send(embed=embed)
                    success_count += 1
                except Exception:
                    failed_count += 1
            else:
                failed_count += 1

        await interaction.followup.send(
            f"✅ **Broadcast Selesai!**\n"
            f"Berhasil terkirim: **{success_count}** server.\n"
            f"Gagal/Tidak ada akses channel: **{failed_count}** server.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(SetupCommands(bot))
