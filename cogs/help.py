import discord
from discord import app_commands
from discord.ext import commands

class CustomHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Menampilkan panduan penggunaan dan daftar tier paket bot")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # FIX DIAGNOSIS: Tarik data Slash Command resmi (lengkap dengan ID) langsung dari server Discord
        try:
            fetched_cmds = await self.bot.tree.fetch_commands()
            cmd_map = {cmd.name: cmd.id for cmd in fetched_cmds}
        except Exception:
            cmd_map = {}

        # Fungsi helper buat ngubah jadi format <slash_command_bisa_diklik>
        def get_cmd(name):
            cmd_id = cmd_map.get(name)
            if cmd_id:
                return f"</{name}:{cmd_id}>"
            return f"`/{name}`"

        embed = discord.Embed(
            title="⚔️ Panduan & Tier Paket Ixiera CoC Bot",
            description=(
                "Selamat datang di **Ixiera CoC Bot**!\n"
                "Gunakan Slash Command di bawah ini sesuai dengan tier lisensi server kamu.\n\n"
                "🌐 **Website:** [ixiera.id](https://ixiera.id)\n"
                "💬 **Upgrade Lisensi / Support:** [Chat WhatsApp Admin](https://wa.me/6285736048626)\n"
                "───────────────"
            ),
            color=discord.Color.from_rgb(88, 101, 242)
        )

        # 🟢 TIER 1: FREE
        embed.add_field(
            name="🟢 **TIER FREE (Fitur Dasar Gratis)**",
            value=(
                f"• {get_cmd('donations')} — Top 5 donatur tertinggi clan\n"
                f"• {get_cmd('inactive')} — Cek member pasif / donasi terendah\n"
                f"• {get_cmd('warstatus')} — Status bintang & destruction war saat ini\n"
                f"• {get_cmd('cwl')} — Cek status & daftar clan di grup Clan War League\n"
                f"• {get_cmd('clanmembers')} — List struktur jabatan clan"
            ),
            inline=False
        )

        # 🔵 TIER 2: STANDAR (Rp10.000/bulan)
        embed.add_field(
            name="🔵 **TIER STANDAR — Rp10.000/bulan (Full Utility & Automation)**",
            value=(
                "• *Semua Fitur Tier Free +*\n"
                f"• {get_cmd('racewar')} — Klasemen stars perang aktif / perang terakhir\n"
                f"• {get_cmd('racecwl')} — Klasemen akumulasi stars CWL bulanan\n"
                f"• {get_cmd('givereward')} — Tandai & berikan reward ke member\n"
                f"• {get_cmd('rewardhistory')} — Histori riwayat reward yang pernah dibagikan\n"
                f"• {get_cmd('memberstats')} — Detail statistik 1 member\n"
                f"• {get_cmd('compare')} — Perbandingan statistik 2 member\n"
                f"• {get_cmd('leaderboard')}, {get_cmd('wartime')}, {get_cmd('thcomposition')}\n"
                "• 🔔 **Auto Alert** — Notifikasi member keluar clan & ping sisa waktu war"
            ),
            inline=False
        )

        # 🟣 TIER 3: AI PRO (Rp30.000/bulan)
        embed.add_field(
            name="🟣 **TIER AI PRO — Rp30.000/bulan (Executive AI Consultant)**",
            value=(
                "• *Semua Fitur Tier Standar +*\n"
                f"• {get_cmd('ai-audit')} — Konsultasi Niki AI: Skor kesehatan clan & fokus pembinaan\n"
                f"• {get_cmd('war-strategy')} — Analisis agregat war saat ini & rotasi attack\n"
                f"• {get_cmd('base-scan')} — Upload screenshot base lawan untuk analisis titik lemah & meta"
            ),
            inline=False
        )

        # ⚙️ SYSTEM
        embed.add_field(
            name="⚙️ **Sistem & Koneksi**",
            value=f"• {get_cmd('setup')} `[clan_tag] [channel_notif]` — Hubungkan bot ke clan CoC",
            inline=False
        )

        embed.set_footer(
            text="Ixiera.id — Operating System Studio"
        )

        # TOMBOL CHAT ADMIN WA & WEBSITE
        view = discord.ui.View()
        wa_button = discord.ui.Button(
            label="Hubungi WhatsApp Admin", 
            url="https://wa.me/6285736048626", 
            style=discord.ButtonStyle.link,
            emoji="💬"
        )
        web_button = discord.ui.Button(
            label="Kunjungi Ixiera.id", 
            url="https://ixiera.id", 
            style=discord.ButtonStyle.link,
            emoji="🌐"
        )
        view.add_item(wa_button)
        view.add_item(web_button)

        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(CustomHelp(bot))
