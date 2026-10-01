import discord
from discord import app_commands
from discord.ext import commands
import io
import csv
from services.db import get_db, check_standar_access
from models import ServerConfig, War, ClanMember
from sqlalchemy import text

from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import matplotlib.pyplot as plt

class RecapCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _generate_csv(self, rows_data):
        output = io.StringIO()
        if not rows_data:
            return None
        fieldnames = list(rows_data[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_data)
        output.seek(0)
        return io.BytesIO(output.getvalue().encode('utf-8'))

    def _create_graph(self, data, title):
        top_data = sorted(data, key=lambda x: x['True Stars'], reverse=True)[:5]
        names = [str(x['Name'])[:10] for x in top_data]
        stars = [x['True Stars'] for x in top_data]

        plt.figure(figsize=(7, 4))
        plt.bar(names, stars, color='#5865F2', edgecolor='black')
        plt.title(f'Top 5 Member (True Stars) - {title}', fontsize=14, fontweight='bold')
        plt.ylabel('True Stars', fontsize=12)
        plt.xlabel('Nama Member', fontsize=12)
        plt.ylim(0, max(stars) + 3 if stars else 10)
        
        for i, v in enumerate(stars):
            plt.text(i, v + 0.5, str(v), ha='center', fontweight='bold')

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        buf.seek(0)
        plt.close()
        return buf

    def _generate_pdf(self, data, clan_tag, is_cwl):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        title_style.alignment = 1
        
        cell_style = ParagraphStyle(name='CellStyle', fontSize=9, leading=11, alignment=1)
        name_style = ParagraphStyle(name='NameStyle', fontSize=9, leading=11, alignment=0) 

        tipe = "CWL Season" if is_cwl else "War Biasa"
        
        elements.append(Paragraph(f"Laporan Analitik Kompetitif {tipe} — {clan_tag}", title_style))
        elements.append(Spacer(1, 20))
        
        graph_buf = self._create_graph(data, tipe)
        elements.append(Image(graph_buf, width=500, height=280))
        elements.append(PageBreak())

        elements.append(Paragraph("Tabel 1: Statistik Serangan (True Stars & Destruksi)", styles['Heading2']))
        elements.append(Spacer(1, 10))
        
        head_offense = ['Rank', 'Nama Member', 'TH', 'Atk', 'True Stars', 'Avg Dest', '3-Stars', 'Missed']
        data_offense = [[Paragraph(h, cell_style) for h in head_offense]]
        
        for idx, row in enumerate(data, 1):
            data_offense.append([
                str(idx),
                Paragraph(str(row['Name']), name_style),
                str(row['Town Hall']),
                str(row['Number of Attacks']),
                f"{int(row['True Stars'] or 0)}⭐",
                f"{float(row['Avg. Dest'] or 0):.1f}%",
                str(row['Three Stars'] or 0),
                str(row['Missed'] or 0)
            ])
            
        t_offense = Table(data_offense, colWidths=[35, 140, 40, 40, 60, 60, 50, 50])
        t_offense.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#5865F2")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'), 
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#EAEAEA")])
        ]))
        elements.append(t_offense)
        elements.append(PageBreak())

        elements.append(Paragraph("Tabel 2: Pertahanan & Indeks Taktis Perang", styles['Heading2']))
        elements.append(Spacer(1, 10))
        
        head_def = ['Nama Member', 'Def Stars', 'Def Dest', 'Avg Tgt Pos', 'Tgt Distance', 'TH Distance']
        data_def = [[Paragraph(h, cell_style) for h in head_def]]
        
        for row in data:
            data_def.append([
                Paragraph(str(row['Name']), name_style),
                f"{int(row['Total Def Stars'] or 0)}⭐",
                f"{float(row['Avg. Def Dest'] or 0):.1f}%",
                str(round(row['Avg. Target Position [1]'] or 0, 1)),
                str(round(row['Avg. Target Distance [2]'] or 0, 1)),
                str(round(row['Avg. TH Distance [3]'] or 0, 1))
            ])
            
        t_def = Table(data_def, colWidths=[160, 60, 60, 70, 70, 70])
        t_def.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#ED4245")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#EAEAEA")])
        ]))
        elements.append(t_def)
        elements.append(Spacer(1, 15))

        catatan_style = ParagraphStyle(name='Notes', fontSize=8.5, leading=12)
        catatan_teks = """
        <b>Panduan Analitik Metrik Kompetitif (Esports Grade):</b><br/>
        <b>[1] Avg. Target Position (ATP):</b> Menunjukkan area map yang sering diserang oleh player. Semakin kecil angkanya (misal: 1-5), berarti player ditugaskan menyerang base inti papan atas musuh.<br/>
        <b>[2] Target Distance Index (TDI):</b> Kedisiplinan serangan berdasarkan urutan map. Angka negatif (misal: -5) berarti player menyerang jatuh ke bawah map (dip). Angka positif (misal: +2) berarti player mampu menyerang base yang lebih tinggi dari posisinya (reach). Angka 0 menunjukkan serangan cermin akurat (mirror).<br/>
        <b>[3] TH Differential (THD):</b> Menilai tingkat kesulitan serangan. Angka -1.0 berarti player selalu menyerang Town Hall 1 level di bawahnya (bully). Angka positif menandakan player mampu meratakan TH yang lebih tinggi dari levelnya sendiri.<br/>
        <b>[4] True Stars / Net Stars (TNS):</b> Bintang murni yang disumbangkan ke total skor klan. Menyerang base yang sudah 2-bintang dan mendapat 3-bintang hanya bernilai 1 True Star (Clean-up point).<br/>
        <b>[5] Fresh Hit Rate (FHR):</b> Rasio keberhasilan menyerang base yang belum pernah disentuh oleh siapapun sebelumnya. Sangat krusial untuk pembuka strategi map klan.<br/>
        <b>[6] Defense Hold Rate (DHR):</b> Kemampuan tata letak (layout) base bertahan dari bintang 3. Base yang mampu menahan 3 serangan sebelum runtuh memiliki nilai DHR yang sangat tinggi.
        """
        elements.append(Paragraph(catatan_teks, catatan_style))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    async def _generate_recap(self, interaction: discord.Interaction, is_cwl: bool):
        guild_id = str(interaction.guild_id)
        
        has_access, err_msg = check_standar_access(guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg)

        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == guild_id).first()
            clan_tag = config.clan_tag
            
            wars = db.query(War).filter(War.clan_tag == clan_tag, War.is_cwl == is_cwl).all()
            if not wars:
                tipe = "CWL" if is_cwl else "War Biasa"
                return await interaction.followup.send(f"❌ Belum ada data akumulasi {tipe} untuk clan `{clan_tag}`.")

            war_ids = [str(w.id) for w in wars]
            war_ids_str = ",".join(war_ids)

            query = text(f"""
                WITH Participants AS (
                    SELECT 
                        player_tag as tag,
                        MAX(player_name) as name,
                        COUNT(DISTINCT war_id) as wars_participated,
                        SUM(attacks_allowed) as total_allowed,
                        SUM(attacks_used) as total_used,
                        SUM(opp_attacks_count) as total_defenses,
                        SUM(best_opp_stars) as total_def_stars,
                        AVG(NULLIF(best_opp_stars, 0)) as avg_def_stars,
                        SUM(best_opp_destruction) as total_def_dest,
                        AVG(NULLIF(best_opp_destruction, 0)) as avg_def_dest
                    FROM war_participants 
                    WHERE war_id IN ({war_ids_str})
                    GROUP BY player_tag
                ),
                Offense AS (
                    SELECT 
                        attacker_tag as tag,
                        MAX(attacker_name) as name,
                        COUNT(id) as total_attacks,
                        SUM(stars) as total_stars,
                        AVG(stars) as avg_stars,
                        SUM(net_stars) as true_stars,
                        SUM(destruction_percentage) as total_dest,
                        AVG(destruction_percentage) as avg_dest,
                        SUM(CASE WHEN stars = 3 THEN 1 ELSE 0 END) as three_stars,
                        SUM(CASE WHEN stars = 2 THEN 1 ELSE 0 END) as two_stars,
                        SUM(CASE WHEN stars = 1 THEN 1 ELSE 0 END) as one_stars,
                        SUM(CASE WHEN stars = 0 THEN 1 ELSE 0 END) as zero_stars,
                        AVG(NULLIF(defender_map_position, 0)) as avg_target_position,
                        AVG(NULLIF(attacker_map_position, 0) - NULLIF(defender_map_position, 0)) as avg_target_distance,
                        AVG(NULLIF(defender_th, 0) - NULLIF(attacker_th, 0)) as avg_th_distance
                    FROM war_attacks 
                    WHERE war_id IN ({war_ids_str})
                    GROUP BY attacker_tag
                ),
                AllTags AS (
                    SELECT tag, name FROM Participants
                    UNION
                    SELECT tag, name FROM Offense
                )
                SELECT 
                    a.name, a.tag, 
                    COALESCE(p.wars_participated, 1) as wars_participated,
                    COALESCE(o.total_attacks, 0) as total_attacks,
                    CASE 
                        WHEN p.tag IS NOT NULL THEN (p.total_allowed - p.total_used)
                        ELSE 0 
                    END as missed_attacks,
                    COALESCE(o.total_stars, 0) as total_stars, 
                    COALESCE(o.avg_stars, 0) as avg_stars,
                    COALESCE(o.true_stars, COALESCE(o.total_stars, 0)) as true_stars,
                    COALESCE(o.total_dest, 0) as total_dest, 
                    COALESCE(o.avg_dest, 0) as avg_dest,
                    COALESCE(o.three_stars, 0) as three_stars, 
                    COALESCE(o.two_stars, 0) as two_stars, 
                    COALESCE(o.one_stars, 0) as one_stars, 
                    COALESCE(o.zero_stars, 0) as zero_stars,
                    COALESCE(o.avg_target_position, 0) as avg_target_position, 
                    COALESCE(o.avg_target_distance, 0) as avg_target_distance, 
                    COALESCE(o.avg_th_distance, 0) as avg_th_distance,
                    COALESCE(p.total_defenses, 0) as total_defenses, 
                    COALESCE(p.total_def_stars, 0) as total_def_stars, 
                    COALESCE(p.avg_def_stars, 0) as avg_def_stars, 
                    COALESCE(p.total_def_dest, 0) as total_def_dest, 
                    COALESCE(p.avg_def_dest, 0) as avg_def_dest
                FROM AllTags a
                LEFT JOIN Participants p ON a.tag = p.tag
                LEFT JOIN Offense o ON a.tag = o.tag
                ORDER BY true_stars DESC, o.avg_dest DESC
            """)
            
            results = db.execute(query).mappings().all()
            if not results:
                return await interaction.followup.send("❌ Belum ada histori serangan tercatat.")

            members_th = {m.tag: m.townhall_level for m in db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).all()}

            csv_data = []
            for row in results:
                th_level = members_th.get(row['tag'], "N/A")
                missed = row['missed_attacks']
                if missed < 0: missed = 0

                csv_data.append({
                    'Name': row['name'],
                    'Tag': row['tag'],
                    'Town Hall': th_level,
                    'Wars Participated': row['wars_participated'],
                    'Number of Attacks': row['total_attacks'],
                    'Total Stars': int(row['total_stars'] or 0),
                    'Avg. Stars': round(row['avg_stars'] or 0, 2),
                    'True Stars': int(row['true_stars'] or 0), 
                    'Avg. True Stars': round((row['true_stars'] / row['total_attacks']) if row['total_attacks'] else 0, 2),
                    'Total Dest': int(row['total_dest'] or 0),
                    'Avg. Dest': round(row['avg_dest'] or 0, 2),
                    'Three Stars': int(row['three_stars'] or 0),
                    'Two Stars': int(row['two_stars'] or 0),
                    'One Stars': int(row['one_stars'] or 0),
                    'Zero Stars': int(row['zero_stars'] or 0),
                    'Missed': missed,
                    'Total Defenses': int(row['total_defenses'] or 0),
                    'Total Def Stars': int(row['total_def_stars'] or 0),
                    'Avg. Def Stars': round(row['avg_def_stars'] or 0, 2),
                    'Total Def Dest': round(row['total_def_dest'] or 0, 2),
                    'Avg. Def Dest': round(row['avg_def_dest'] or 0, 2),
                    'Avg. Target Position [1]': round(row['avg_target_position'] or 0, 2),
                    'Avg. Target Distance [2]': round(row['avg_target_distance'] or 0, 2),
                    'Avg. TH Distance [3]': round(row['avg_th_distance'] or 0, 2)
                })

            tipe_file = "CWL" if is_cwl else "War"
            
            csv_buffer = self._generate_csv(csv_data)
            pdf_buffer = self._generate_pdf(csv_data, clan_tag.replace('#', ''), is_cwl)
            
            file_csv = discord.File(fp=csv_buffer, filename=f"Data_Lengkap_{tipe_file}_{clan_tag.replace('#', '')}.csv")
            file_pdf = discord.File(fp=pdf_buffer, filename=f"Laporan_Komprehensif_{tipe_file}_{clan_tag.replace('#', '')}.pdf")

            embed = discord.Embed(
                title=f"📊 Laporan Analitik {tipe_file} — {clan_tag}",
                description=f"Total Perang Tercatat: **{len(wars)} War**\nDokumen ringkasan analitik visual dan lembar data mentah telah dilampirkan.",
                color=discord.Color.purple() if is_cwl else discord.Color.blue()
            )
            
            embed.set_footer(text="ixiera.id — Operating System Studio | WA: https://wa.me/6285736048626")
            await interaction.followup.send(embed=embed, files=[file_pdf, file_csv])

        except Exception as e:
            db.rollback()
            await interaction.followup.send(f"❌ Terjadi kesalahan saat memproses data: {e}")
        finally:
            db.close()

    @app_commands.command(name="rekap-cwl", description="[MEMBER+] Unduh laporan komprehensif performa CWL clan")
    async def rekap_cwl(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._generate_recap(interaction, is_cwl=True)

    @app_commands.command(name="rekap-war", description="[MEMBER+] Unduh laporan komprehensif performa War Biasa clan")
    async def rekap_war(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._generate_recap(interaction, is_cwl=False)

async def setup(bot):
    await bot.add_cog(RecapCommands(bot))
