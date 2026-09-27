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
                "• `/cwl` — Cek status & daftar clan di grup Clan War League\n"
                "• `/clanmembers` — List struktur jabatan clan"
            ),
            inline=False
        )

        # 🔵 TIER 2: STANDAR (Rp10k/bln)
        embed.add_field(
            name="🔵 **TIER STANDAR — Rp10.000/bln (Full Utility & Automation)**",
            value=(
                "• *Semua Fitur Tier Free +*\n"
                "• `/racewar` — Klasemen stars perang aktif / perang terakhir\n"
                "• `/racecwl` — Klasemen akumulasi stars CWL bulanan\n"
                "• `/givereward` — Tandai & berikan reward ke member\n"
                "• `/rewardhistory` — Histori riwayat reward yang pernah dibagikan\n"
                "• `/memberstats` — Detail statistik 1 member\n"
                "• `/compare` — Perbandingan statistik 2 member\n"
                "• `/leaderboard`, `/wartime`, `/thcomposition`\n"
                "• 🔔 **Auto Alert** — Notifikasi member keluar clan & ping sisa waktu war"
            ),
            inline=False
        )

        # 🟣 TIER 3: AI PRO (Rp30k/bln)
        embed.add_field(
            name="🟣 **TIER AI PRO — Rp30.000/bln (Executive AI Consultant)**",
            value=(
                "• *Semua Fitur Tier Standar +*\n"
                "• `/ai-audit` — Konsultasi Niki AI: Skor kesehatan clan & fokus pembinaan\n"
                "• `/war-strategy` — Analisis agregat war saat ini & rotasi attack\n"
                "• `/base-scan` — Upload screenshot base lawan untuk analisis titik lemah & meta"
            ),
            inline=False
        )

        # ⚙️ SYSTEM
        embed.add_field(
            name="⚙️ **Sistem & Koneksi**",
            value="• `/setup [clan_tag] [channel_notif]` — Hubungkan bot ke clan CoC",
            inline=False
        )

        # FOOTER BRANDING + WA
        embed.set_footer(
            text="ixiera.id — Operating System Studio | WA: https://wa.me/6285736048626"
        )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CustomHelp(bot))
