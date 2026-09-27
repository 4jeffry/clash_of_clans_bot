import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

from services.db import get_db
from models import ServerConfig

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 1. COMMAND CLEAR / PURGE CHAT
    @app_commands.command(name="clear", description="[ADMIN] Menghapus pesan di channel ini secara masal")
    @app_commands.describe(amount="Jumlah pesan yang ingin dihapus (maksimal 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int = 10):
        if amount > 100:
            amount = 100
            
        await interaction.response.defer(thinking=True, ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 Berhasil menghapus **{len(deleted)}** pesan di channel ini.", ephemeral=True)

    # 2. COMMAND CEK STATUS LISENSI / USAGE TIER
    @app_commands.command(name="usage", description="Cek status lisensi, masa aktif tier, dan konfigurasi server saat ini")
    async def usage(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(interaction.guild_id)).first()
            
            if not config:
                await interaction.followup.send("❌ Server ini belum terhubung ke clan CoC! Jalankan `/setup` terlebih dahulu.")
                return

            tier_status = str(config.tier).upper() if config.tier else "FREE"
            clan_tag = config.clan_tag or "Belum diatur"
            
            # Format tanggal expired (Disesuaikan dengan models.py: expired_at)
            if config.expired_at:
                if isinstance(config.expired_at, datetime):
                    exp_date = config.expired_at.strftime("%d %B %Y, %H:%M WIB")
                    days_left = (config.expired_at - datetime.now(timezone.utc).replace(tzinfo=None)).days
                else:
                    exp_date = str(config.expired_at)
                    days_left = "N/A"
                
                status_exp = f"`{exp_date}` ({days_left} hari tersisa)" if days_left != "N/A" and days_left >= 0 else f"`{exp_date}` (Kadaluarsa)"
            else:
                status_exp = "♾️ Permanen (Tier Gratis)"

            embed = discord.Embed(
                title=f"📊 Status Lisensi & Usage — {interaction.guild.name}",
                color=discord.Color.blue() if tier_status == "FREE" else discord.Color.gold()
            )
            
            embed.add_field(name="🏷️ Tier Paket Saat Ini", value=f"**{tier_status}**", inline=True)
            embed.add_field(name="🛡️ Clan Tag Terhubung", value=f"`{clan_tag}`", inline=True)
            embed.add_field(name="⏳ Masa Aktif / Expired", value=status_exp, inline=False)
            
            if tier_status == "FREE":
                embed.add_field(
                    name="💡 Mau Upgrade Fitur AI & Otomatisasi?",
                    value="Hubungi Admin untuk upgrade ke **Tier Standar** (Rp10k) atau **AI Pro** (Rp30k).\n💬 [Chat WhatsApp Admin](https://wa.me/6285736048626)",
                    inline=False
                )

            embed.set_footer(text="Niki CoC Bot — Executive AI Consultant")
            await interaction.followup.send(embed=embed)

        finally:
            db.close()

    @clear.error
    async def clear_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ Lu gak punya izin *Manage Messages* buat pakai command ini!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Terjadi kesalahan: {error}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
