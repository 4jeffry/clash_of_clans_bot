import discord
from discord import app_commands
from discord.ext import commands

class CustomHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Menampilkan panduan penggunaan dan daftar perintah bot")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed = discord.Embed(
            title="⚔️ Panduan & Daftar Command  CoC Bot",
            description=(
                "Selamat datang di ** CoC AI Assistant**!\n"
                "Gunakan Slash Command (`/`) di bawah ini untuk mengelola clan kamu.\n"
                "───────────────"
            ),
            color=discord.Color.from_rgb(88, 101, 242)
        )

        # Kategori AI Pro
        embed.add_field(
            name="🟣 **AI Pro Features (Gemini Intelligence)**",
            value=(
                "• `/ai-audit` — Deep audit kesehatan clan & rekomendasi member pasif\n"
                "• `/war-strategy` — Analisis taktik & rekomendasi pemetaan serangan war"
            ),
            inline=False
        )

        # Kategori Member & Analytics (Standar)
        embed.add_field(
            name="👥 **Member & Clan Analytics**",
            value=(
                "• `/donations` — Top 5 donatur tertinggi di clan\n"
                "• `/inactive` — Cek member pasif / donasi terendah\n"
                "• `/memberstats [nama]` — Detail statistik lengkap 1 member\n"
                "• `/compare [m1] [m2]` — Bandingkan performa 2 member\n"
                "• `/leaderboard` — Ranking trophies tertinggi clan"
            ),
            inline=False
        )

        # Kategori War & Automation (Standar)
        embed.add_field(
            name="⚔️ **War & Clan Overview**",
            value=(
                "• `/warstatus` — Status bintang & destruction clan war saat ini\n"
                "• `/wartime` — Sisa waktu war & sisa attack yang belum dipakai\n"
                "• `/clanmembers` — List lengkap struktur jabatan clan\n"
                "• `/thcomposition` — Breakdown jumlah member per level TH\n"
                "• 🔔 *Auto War Alert (Leader Ping) aktif otomatis di Tier Standar*"
            ),
            inline=False
        )

        # Kategori System
        embed.add_field(
            name="⚙️ **System & Setup (Admin Only)**",
            value="• `/setup [clan_tag]` — Binding bot ke Tag Clan CoC server ini",
            inline=False
        )

        embed.set_footer(
            text="Operating System Studio",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
        )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CustomHelp(bot))
