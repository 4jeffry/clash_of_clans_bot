import discord
from discord import app_commands
from discord.ext import commands

class CustomHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Menampilkan panduan penggunaan dan cara mendukung bot")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            fetched_cmds = await self.bot.tree.fetch_commands()
            cmd_map = {cmd.name: cmd.id for cmd in fetched_cmds}
        except Exception:
            cmd_map = {}

        def get_cmd(name):
            cmd_id = cmd_map.get(name)
            if cmd_id:
                return f"</{name}:{cmd_id}>"
            return f"`/{name}`"

        embed = discord.Embed(
            title="⚔️ Panduan & Dukungan Niki CoC Bot",
            description=(
                "Selamat datang di **Niki CoC Bot**!\n"
                "Bot komunitas independen untuk manajemen Clan Clash of Clans.\n\n"
                "💬 **Bantu Donasi / Support:** [Chat WhatsApp Admin](https://wa.me/6285736048626)\n"
                "───────────────"
            ),
            color=discord.Color.from_rgb(88, 101, 242)
        )

        embed.add_field(
            name="🟢 **AKSES PUBLIK (Gratis)**",
            value=(
                f"• {get_cmd('donations')} — Top 5 donatur tertinggi clan\n"
                f"• {get_cmd('inactive')} — Cek member pasif / donasi terendah\n"
                f"• {get_cmd('warstatus')} — Status bintang & destruction war\n"
                f"• {get_cmd('cwl')} — Cek status clan di grup CWL\n"
                f"• {get_cmd('clanmembers')} — List struktur jabatan clan\n"
                f"• {get_cmd('capital')} — Ringkasan Raid Clan Capital\n"
                f"• {get_cmd('capitaldonations')} — Top donatur Capital Gold\n"
                f"• {get_cmd('raidstats')} — Status serangan Raid Weekend"
            ),
            inline=False
        )

        embed.add_field(
            name="🔵 **MEMBER+ SUPPORTER (Donasi Server Rp10k/bln)**",
            value=(
                "*(Terima kasih telah membantu biaya server kami!)*\n"
                f"• {get_cmd('rekap-war')} — Unduh laporan lengkap performa & taktik War 1 Bulan\n"
                f"• {get_cmd('rekap-cwl')} — Unduh laporan komprehensif performa CWL 7 Hari\n"
                f"• {get_cmd('racewar')} — Klasemen Offense & Defense perang aktif\n"
                f"• {get_cmd('racecwl')} — Klasemen Offense & Defense CWL berjalan\n"
                f"• {get_cmd('givereward')} — Berikan reward ke member\n"
                f"• {get_cmd('rewardhistory')} — Histori pembagian reward\n"
                f"• {get_cmd('memberstats')} — Detail statistik 1 member\n"
                f"• {get_cmd('compare')} — Perbandingan statistik 2 member\n"
                f"• {get_cmd('leaderboard')}, {get_cmd('wartime')}, {get_cmd('thcomposition')}\n"
                "• 🔔 **Auto Alert** — Notifikasi member keluar/masuk & sisa waktu war"
            ),
            inline=False
        )

        embed.add_field(
            name="🟣 **VIP SUPPORTER (Akses AI - Donasi Rp30k/bln)**",
            value=(
                "*(Dukungan ekstra untuk menutupi biaya AI)*\n"
                f"• {get_cmd('ai-audit')} — Audit kesehatan clan & evaluasi member\n"
                f"• {get_cmd('ai-screen')} — Intel profil calon member sebelum di-acc\n"
                f"• {get_cmd('ai-scout')} — Intel war lawan & target base paling rentan\n"
                f"• {get_cmd('war-strategy')} — Analisis agregat war saat ini\n"
                f"• {get_cmd('base-scan')} — Upload foto base musuh untuk cari titik lemah"
            ),
            inline=False
        )

        embed.add_field(
            name="⚙️ **Sistem & Moderasi**",
            value=(
                f"• {get_cmd('setup')} `[clan_tag] [channel_notif]` — Hubungkan bot ke clan\n"
                f"• {get_cmd('usage')} — Cek status donatur & masa aktif server\n"
                f"• {get_cmd('clear')} `[amount]` — [ADMIN] Hapus chat secara masal"
            ),
            inline=False
        )

        embed.set_footer(
            text="This material is unofficial and is not endorsed by Supercell.\nFor more information see Supercell's Fan Content Policy."
        )

        view = discord.ui.View()
        wa_button = discord.ui.Button(
            label="Hubungi WhatsApp Admin", 
            url="https://wa.me/6285736048626", 
            style=discord.ButtonStyle.link,
            emoji="💬"
        )
        view.add_item(wa_button)

        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(CustomHelp(bot))
