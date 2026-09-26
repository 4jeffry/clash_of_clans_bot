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
            title="⚔️ Panduan & Daftar Command Ixiera CoC Bot",
            description=(
                "Selamat datang di **Ixiera CoC AI Assistant**!\n"
                "Gunakan Slash Command (`/`) di bawah ini atau **mention bot langsung** untuk ngobrol pakai AI.\n"
                "───────────────"
            ),
            color=discord.Color.from_rgb(88, 101, 242) # Warna Blurple khas Discord
        )

        # Kategori AI
        embed.add_field(
            name="🤖 **AI Assistant & Analytics**",
            value=(
                "• `/ask [pertanyaan]` — Tanya strategi, base, atau analisis clan ke Gemini\n"
                "• `@clan_bot [pesan]` — Ngobrol langsung/tanya siapa member pasif"
            ),
            inline=False
        )

        # Kategori Member & Analytics
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

        # Kategori War & Management
        embed.add_field(
            name="⚔️ **War & Clan Overview**",
            value=(
                "• `/warstatus` — Status bintang & destruction clan war saat ini\n"
                "• `/wartime` — Sisa waktu war & sisa attack yang belum dipakai\n"
                "• `/clanmembers` — List lengkap struktur jabatan clan\n"
                "• `/thcomposition` — Breakdown jumlah member per level TH\n"
                "• `/clanstats` — Ringkasan umum statistik clan"
            ),
            inline=False
        )

        # Kategori Admin
        embed.add_field(
            name="⚙️ **System & Setup (Admin Only)**",
            value="• `/setup [clan_tag]` — Binding bot ke Tag Clan CoC server ini",
            inline=False
        )

        embed.set_footer(
            text="ixiera.id • Operating System Studio",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
        )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CustomHelp(bot))
