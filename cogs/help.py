import discord
from discord import app_commands
from discord.ext import commands

class CustomHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Menampilkan panduan penggunaan dan daftar tier paket bot")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed = discord.Embed(
            title="⚔️ Panduan & Tier Paket Ixiera CoC Bot",
            description=(
                "Selamat datang di **Ixiera CoC Bot**!\n"
                "Gunakan Slash Command (`/`) di bawah ini sesuai dengan tier lisensi server kamu.\n"
                "───────────────"
            ),
            color=discord.Color.from_rgb(88, 101, 242)
        )

        # 🟢 TIER 1: FREE
        embed.add_field(
            name="🟢 **TIER FREE (Fitur Dasar)**",
            value=(
                "• `/donations` — Top 5 donatur tertinggi clan\n"
                "• `/inactive` — Cek member pasif / donasi terendah\n"
                "• `/warstatus` — Status bintang & destruction war saat ini\n"
                "• `/clanmembers` — List struktur jabatan clan"
            ),
            inline=False
        )

        # 🔵 TIER 2: STANDAR (Rp10k/bln)
        embed.add_field(
            name="🔵 **TIER STANDAR — Rp10.000/bln (Full Utility & Automation)**",
            value=(
                "• *Semua Fitur Tier Free +*\n"
                "• `/memberstats [nama]` — Detail statistik lengkap 1 member\n"
                "• `/compare [m1] [m2]` — Perbandingan statistik 2 member\n"
                "• `/leaderboard` — Ranking trophies tertinggi clan\n"
                "• `/wartime` — Sisa waktu war & sisa attack yang belum dipakai\n"
                "• `/thcomposition` — Breakdown jumlah member per level TH\n"
                "• 🔔 **Auto War Alert** — Ping otomatis ke Leader/Co-Leader 2 jam sebelum war selesai (mengingatkan member in-game yang belum attack)"
            ),
            inline=False
        )

        # 🟣 TIER 3: AI PRO (Rp30k/bln)
        embed.add_field(
            name="🟣 **TIER AI PRO — Rp30.000/bln (Executive AI Consultant)**",
            value=(
                "• *Semua Fitur Tier Standar +*\n"
                "• `/ai-audit` — Deep Audit Gemini: Skor kesehatan clan, rekomendasi kick member pensi, & action plan\n"
                "• `/war-strategy` — Konsultan Taktik Gemini: Analisis kelemahan lawan & draf broadcast chat CoC"
            ),
            inline=False
        )

        # ⚙️ SYSTEM & UPGRADE
        embed.add_field(
            name="⚙️ **Sistem & Upgrade Lisensi**",
            value=(
                "• `/setup [clan_tag]` — Hubungkan bot ke clan CoC (Admin Only)\n"
                "💳 *Untuk upgrade ke Tier Standar/Pro, hubungi Admin (`ixiera.id`)*"
            ),
            inline=False
        )

        embed.set_footer(
            text="ixiera.id • Operating System Studio",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
        )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CustomHelp(bot))
