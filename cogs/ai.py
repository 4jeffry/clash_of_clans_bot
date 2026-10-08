import discord
import io
from discord import app_commands
from discord.ext import commands
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from services.llm_client import (
    run_ai_audit, 
    run_war_strategy, 
    run_ai_screen, 
    run_ai_scout,
    run_ai_opponent,
    run_ai_report
)
from services.coc_client import CoCClient
from services.db import get_db
from models import ServerConfig

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.coc = CoCClient()

    def get_clan_tag(self, guild_id):
        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(guild_id)).first()
            return config.clan_tag if config else None
        finally:
            db.close()
            
    async def send_as_pdf(self, interaction: discord.Interaction, title: str, text: str):
        """Membuat dan mengirim output AI sebagai file PDF menggunakan reportlab."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        
        custom_style = ParagraphStyle(
            'CustomText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=11,
            leading=16,
            spaceAfter=6
        )
        title_style = styles['Heading1']

        story = []
        clean_title = title.replace('_', ' ').upper()
        story.append(Paragraph(f"LAPORAN AI: {clean_title}", title_style))
        story.append(Spacer(1, 15))

        # Pecah teks dari AI per baris agar rapi di PDF
        for line in text.split('\n'):
            if line.strip() == '':
                story.append(Spacer(1, 8))
            else:
                # Escape karakter khusus XML agar reportlab tidak error
                safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(safe_line, custom_style))

        doc.build(story)
        buffer.seek(0)
        
        filename = f"{title.replace(' ', '_').lower()}.pdf"
        discord_file = discord.File(fp=buffer, filename=filename)
        
        embed = discord.Embed(
            title=f"📄 Dokumen AI: {clean_title}",
            description="Laporan berhasil dibuat. Silakan unduh dokumen PDF di bawah ini.",
            color=discord.Color.red()
        )
        embed.set_footer(text="ixiera.id — AI Executive Systems")
        await interaction.followup.send(embed=embed, file=discord_file)

    async def _get_smart_war_data(self, clan_tag: str):
        try:
            war_data = await self.coc.get_current_war(clan_tag)
            if war_data and isinstance(war_data, dict) and war_data.get('state') in ['inWar', 'preparation']:
                return war_data
        except Exception:
            pass

        try:
            cwl_group = await self.coc.get_cwl_group(clan_tag)
            if cwl_group and isinstance(cwl_group, dict) and cwl_group.get('state') != 'notInWar':
                rounds = cwl_group.get('rounds', [])
                prep_war = None
                for r in reversed(rounds):
                    for w_tag in r.get('warTags', []):
                        if w_tag == '#0': continue
                        cwl_war = await self.coc.get_cwl_war(w_tag)
                        if cwl_war and isinstance(cwl_war, dict):
                            t1 = cwl_war.get('clan', {}).get('tag')
                            t2 = cwl_war.get('opponent', {}).get('tag')
                            
                            if t1 == clan_tag or t2 == clan_tag:
                                if t2 == clan_tag:
                                    cwl_war['clan'], cwl_war['opponent'] = cwl_war['opponent'], cwl_war['clan']
                                state = cwl_war.get('state')
                                if state == 'inWar':
                                    return cwl_war
                                elif state == 'preparation' and not prep_war:
                                    prep_war = cwl_war
                if prep_war:
                    return prep_war
        except Exception:
            pass
        return None

    async def _get_latest_finished_war(self, clan_tag: str):
        try:
            cwl_group = await self.coc.get_cwl_group(clan_tag)
            if cwl_group and isinstance(cwl_group, dict) and cwl_group.get('state') != 'notInWar':
                rounds = cwl_group.get('rounds', [])
                for r in reversed(rounds):
                    for w_tag in r.get('warTags', []):
                        if w_tag == '#0': continue
                        cwl_war = await self.coc.get_cwl_war(w_tag)
                        if cwl_war and isinstance(cwl_war, dict) and cwl_war.get('state') == 'warEnded':
                            t1 = cwl_war.get('clan', {}).get('tag')
                            t2 = cwl_war.get('opponent', {}).get('tag')
                            if t1 == clan_tag or t2 == clan_tag:
                                if t2 == clan_tag:
                                    cwl_war['clan'], cwl_war['opponent'] = cwl_war['opponent'], cwl_war['clan']
                                return cwl_war
        except Exception:
            pass
            
        war_logs = await self.coc.get_war_log(clan_tag)
        if war_logs and isinstance(war_logs, list) and len(war_logs) > 0:
            return war_logs[0]
        return None

    @app_commands.command(name="ai-audit", description="[AI PRO] Audit kesehatan klan & evaluasi member (Cetak PDF)")
    async def ai_audit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        result = await run_ai_audit(str(interaction.guild_id))
        await self.send_as_pdf(interaction, "Audit_Kesehatan_Klan", result)

    @app_commands.command(name="war-strategy", description="[AI PRO] Taktik agregat rotasi attack CWL/War (Cetak PDF)")
    async def ai_war_strategy(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")
        war_data = await self._get_smart_war_data(clan_tag)
        result = await run_war_strategy(str(interaction.guild_id), war_data)
        await self.send_as_pdf(interaction, "Strategi_Perang_Aktif", result)

    @app_commands.command(name="ai-report", description="[AI PRO] Evaluasi performa member & MVP pasca CWL/War (Cetak PDF)")
    async def ai_report(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")
        latest_war = await self._get_latest_finished_war(clan_tag)
        if not latest_war:
            return await interaction.followup.send("❌ Tidak ada data perang atau CWL yang baru saja selesai.")
        result = await run_ai_report(str(interaction.guild_id), latest_war)
        await self.send_as_pdf(interaction, "Laporan_Evaluasi_Pasca_Perang", result)

    @app_commands.command(name="ai-screen", description="[AI PRO] Intel profil calon member sebelum di-acc (Cetak PDF)")
    @app_commands.describe(player_tag="Tag player calon member (cth: #ABC1234)")
    async def ai_screen(self, interaction: discord.Interaction, player_tag: str):
        await interaction.response.defer()
        if not player_tag.startswith('#'):
            player_tag = f"#{player_tag}"
        player_data = await self.coc.get_player_info(player_tag)
        if not player_data or 'tag' not in player_data:
            return await interaction.followup.send("❌ Data player tidak ditemukan!")
        result = await run_ai_screen(str(interaction.guild_id), player_data)
        await self.send_as_pdf(interaction, f"Screening_Member_{player_data.get('name')}", result)

    @app_commands.command(name="ai-scout", description="[AI PRO] Intel CWL/War lawan: cari target base terlemah (Cetak PDF)")
    async def ai_scout(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")
        war_data = await self._get_smart_war_data(clan_tag)
        if not war_data or war_data.get('state') not in ['inWar', 'preparation']:
            return await interaction.followup.send("❌ Clan sedang tidak dalam periode War atau CWL aktif!")
        result = await run_ai_scout(str(interaction.guild_id), war_data)
        await self.send_as_pdf(interaction, "Scouting_Target_Lawan", result)

    @app_commands.command(name="ai-opponent", description="[AI PRO] Estimasi peluang menang vs klan lawan (Cetak PDF)")
    async def ai_opponent(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")
        war_data = await self._get_smart_war_data(clan_tag)
        if not war_data or war_data.get('state') not in ['inWar', 'preparation']:
            return await interaction.followup.send("❌ Clan sedang tidak dalam periode War atau CWL aktif!")
        result = await run_ai_opponent(str(interaction.guild_id), clan_tag, war_data)
        await self.send_as_pdf(interaction, "Estimasi_Peluang_Menang", result)

async def setup(bot):
    await bot.add_cog(AICog(bot))
