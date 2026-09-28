import discord
from discord import app_commands
from discord.ext import commands
import io
import csv
from services.db import get_db, check_standar_access
from models import ServerConfig, War, ClanMember
from sqlalchemy import text

# Import untuk PDF Generation
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

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

    def _generate_pdf(self, data, clan_tag, is_cwl):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        
        styles = getSampleStyleSheet()
        tipe = "CWL Season" if is_cwl else "War Biasa"
        title_text = f"Laporan Performa {tipe} - {clan_tag}"
        
        elements.append(Paragraph(title_text, styles['Title']))
        elements.append(Spacer(1, 12))
        
        # Kolom Ringkasan Eksekutif untuk PDF agar muat di kertas A4
        headers = ['Rank', 'Nama Member', 'TH', 'Atk', 'Stars', 'Avg Dest', 'Missed', 'Def Stars', 'Def Dest']
        table_data = [headers]
        
        for idx, row in enumerate(data, 1):
            nama = str(row['Name'])[:15] + ".." if len(str(row['Name'])) > 15 else str(row['Name'])
            table_data.append([
                str(idx),
                nama,
                str(row['Town Hall']),
                str(row['Number of Attacks']),
                f"{row['Total Stars']}⭐",
                f"{row['Avg. Dest']}%",
                str(row['Missed']),
                f"{row['Total Def Stars']}⭐",
                f"{row['Avg. Def Dest']}%"
            ])
            
        # Styling Tabel PDF biar elegan
        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#5865F2")), # Warna Header Discord
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F6F6F7")),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#EAEAEA")]) # Efek Belang-belang
        ]))
        
        elements.append(t)
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

            max_atk = 1 if is_cwl else 2

            query = text(f"""
                WITH Offense AS (
                    SELECT 
                        attacker_tag as tag, 
                        MAX(attacker_name) as name,
                        COUNT(DISTINCT war_id) as wars_participated,
                        COUNT(id) as total_attacks,
                        SUM(stars) as total_stars,
                        AVG(stars) as avg_stars,
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
                Defense AS (
                    SELECT 
                        defender_tag as tag,
                        COUNT(id) as total_defenses,
                        SUM(stars) as total_def_stars,
                        AVG(stars) as avg_def_stars,
                        SUM(destruction_percentage) as total_def_dest,
                        AVG(destruction_percentage) as avg_def_dest
                    FROM war_attacks 
                    WHERE war_id IN ({war_ids_str})
                    GROUP BY defender_tag
                )
                SELECT 
                    o.name, o.tag, o.wars_participated, o.total_attacks,
                    o.total_stars, o.avg_stars, o.total_dest, o.avg_dest,
                    o.three_stars, o.two_stars, o.one_stars, o.zero_stars,
                    o.avg_target_position, o.avg_target_distance, o.avg_th_distance,
                    COALESCE(d.total_defenses, 0) as total_defenses, 
                    COALESCE(d.total_def_stars, 0) as total_def_stars, 
                    COALESCE(d.avg_def_stars, 0) as avg_def_stars, 
                    COALESCE(d.total_def_dest, 0) as total_def_dest, 
                    COALESCE(d.avg_def_dest, 0) as avg_def_dest
                FROM Offense o
                LEFT JOIN Defense d ON o.tag = d.tag
                ORDER BY o.total_stars DESC, o.avg_dest DESC
            """)
            
            results = db.execute(query).mappings().all()
            if not results:
                return await interaction.followup.send("❌ Belum ada histori serangan tercatat.")

            members_th = {m.tag: m.townhall_level for m in db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).all()}

            csv_data = []
            for row in results:
                th_level = members_th.get(row['tag'], "N/A")
                missed = (row['wars_participated'] * max_atk) - row['total_attacks']
                if missed < 0: missed = 0

                csv_data.append({
                    'Name': row['name'],
                    'Tag': row['tag'],
                    'Town Hall': th_level,
                    'Wars Participated': row['wars_participated'],
                    'Number of Attacks': row['total_attacks'],
                    'Total Stars': row['total_stars'],
                    'Avg. Stars': round(row['avg_stars'], 2) if row['avg_stars'] else 0,
                    'True Stars': row['total_stars'], 
                    'Avg. True Stars': round(row['avg_stars'], 2) if row['avg_stars'] else 0,
                    'Total Dest': row['total_dest'],
                    'Avg. Dest': round(row['avg_dest'], 2) if row['avg_dest'] else 0,
                    'Three Stars': row['three_stars'],
                    'Two Stars': row['two_stars'],
                    'One Stars': row['one_stars'],
                    'Zero Stars': row['zero_stars'],
                    'Missed': missed,
                    'Total Defenses': row['total_defenses'],
                    'Total Def Stars': row['total_def_stars'],
                    'Avg. Def Stars': round(row['avg_def_stars'], 2) if row['avg_def_stars'] else 0,
                    'Total Def Dest': row['total_def_dest'],
                    'Avg. Def Dest': round(row['avg_def_dest'], 2) if row['avg_def_dest'] else 0,
                    'Avg. Target Position [1]': round(row['avg_target_position'], 2) if row['avg_target_position'] else 0,
                    'Avg. Target Distance [2]': round(row['avg_target_distance'], 2) if row['avg_target_distance'] else 0,
                    'Avg. TH Distance [3]': round(row['avg_th_distance'], 2) if row['avg_th_distance'] else 0
                })

            tipe_file = "CWL" if is_cwl else "War"
            
            # GENERATE CSV & PDF BERBARENGAN
            csv_buffer = self._generate_csv(csv_data)
            pdf_buffer = self._generate_pdf(csv_data, clan_tag.replace('#', ''), is_cwl)
            
            file_csv = discord.File(fp=csv_buffer, filename=f"Data_Lengkap_{tipe_file}_{clan_tag.replace('#', '')}.csv")
            file_pdf = discord.File(fp=pdf_buffer, filename=f"Laporan_Tabel_{tipe_file}_{clan_tag.replace('#', '')}.pdf")

            embed = discord.Embed(
                title=f"📊 Laporan Akumulasi {tipe_file} — {clan_tag}",
                description=f"Total Perang Tercatat: **{len(wars)} War**\nFile **PDF** (Ringkasan) dan **CSV** (Data Full 23 Kolom) telah dilampirkan.",
                color=discord.Color.purple() if is_cwl else discord.Color.blue()
            )
            
            top_3 = ""
            for i, item in enumerate(csv_data[:3], 1):
                top_3 += f"**#{i} {item['Name']}**\n└ ⚔️ {item['Total Stars']}⭐ ({item['Avg. Dest']}%) | 🛡️ Def: {item['Total Def Stars']}⭐\n"
            
            embed.add_field(name="🥇 Top 3 Member", value=top_3 or "Kosong", inline=False)
            
            catatan = (
                "**Keterangan Metrik Tambahan (Lihat di CSV):**\n"
                "`[1]` **Avg. Target Position:** Rata-rata posisi map musuh yang diserang.\n"
                "`[2]` **Avg. Target Distance:** Selisih posisi map penyerang vs musuh.\n"
                "`[3]` **Avg. TH Distance:** Selisih level TH penyerang vs musuh."
            )
            embed.add_field(name="📝 Catatan Laporan", value=catatan, inline=False)
            embed.set_footer(text="Niki CoC Bot — Supporter Analytics System")

            # Kirim Embed beserta DUA FILE sekaligus!
            await interaction.followup.send(embed=embed, files=[file_pdf, file_csv])

        except Exception as e:
            db.rollback()
            await interaction.followup.send(f"❌ Terjadi kesalahan saat memproses data: {e}")
        finally:
            db.close()

    @app_commands.command(name="rekap-cwl", description="[MEMBER+] Rekap akumulasi performa CWL (Export PDF & CSV)")
    async def rekap_cwl(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._generate_recap(interaction, is_cwl=True)

    @app_commands.command(name="rekap-war", description="[MEMBER+] Rekap akumulasi performa War Biasa (Export PDF & CSV)")
    async def rekap_war(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._generate_recap(interaction, is_cwl=False)

async def setup(bot):
    await bot.add_cog(RecapCommands(bot))
