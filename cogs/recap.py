import discord
from discord import app_commands
from discord.ext import commands
import io
import csv
from services.db import get_db
from models import ServerConfig, War, WarAttack, CWLSeason
from sqlalchemy import func

class RecapCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _generate_csv(self, rows_data):
        """Helper untuk mengubah list dictionary menjadi file CSV di memory"""
        output = io.StringIO()
        if not rows_data:
            return None
            
        fieldnames = list(rows_data[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_data)
        
        output.seek(0)
        return io.BytesIO(output.getvalue().encode('utf-8'))

    @app_commands.command(name="rekap-cwl", description="[VIP] Rekap akumulasi performa CWL season ini (Export CSV)")
    async def rekap_cwl(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild_id = str(interaction.guild_id)
        
        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == guild_id).first()
            if not config or not config.clan_tag:
                return await interaction.followup.send("❌ Server belum di-setup! Gunakan `/setup` terlebih dahulu.")

            # Cek Lisensi (Hanya VIP / AI Pro)
            tier_status = str(config.tier).lower() if config.tier else "free"
            if tier_status not in ["pro", "ai_pro"]:
                return await interaction.followup.send(
                    "⚠️ **Fitur VIP Exclusive**\n"
                    "Ekspor Laporan Akumulasi CWL (CSV) khusus untuk **VIP Supporter**.\n"
                    "Hubungi Admin untuk upgrade lisensi server kamu!"
                )

            clan_tag = config.clan_tag
            
            # Ambil Season CWL Terakhir
            cwl_wars = db.query(War).filter(
                War.clan_tag == clan_tag,
                War.is_cwl == True
            ).all()

            if not cwl_wars:
                return await interaction.followup.send(f"❌ Belum ada data akumulasi CWL yang tersimpan di database untuk clan `{clan_tag}`.")

            war_ids = [w.id for w in cwl_wars]

            # Query Agregat Serangan Member
            attacks = db.query(
                WarAttack.attacker_name,
                WarAttack.attacker_tag,
                func.count(WarAttack.id).label('total_attacks'),
                func.sum(WarAttack.stars).label('total_stars'),
                func.avg(WarAttack.stars).label('avg_stars'),
                func.sum(WarAttack.destruction_percentage).label('total_dest'),
                func.avg(WarAttack.destruction_percentage).label('avg_dest')
            ).filter(WarAttack.war_id.in_(war_ids))\
             .group_by(WarAttack.attacker_name, WarAttack.attacker_tag)\
             .order_by(func.sum(WarAttack.stars).desc(), func.avg(WarAttack.destruction_percentage).desc())\
             .all()

            if not attacks:
                return await interaction.followup.send("❌ Belum ada histori serangan CWL yang tercatat.")

            # Susun Data CSV
            csv_data = []
            for idx, atk in enumerate(attacks, 1):
                csv_data.append({
                    'Rank': idx,
                    'Nama Member': atk.attacker_name,
                    'Tag Member': atk.attacker_tag,
                    'Total Attack': atk.total_attacks,
                    'Total Stars': atk.total_stars,
                    'Avg Stars': round(atk.avg_stars, 2) if atk.avg_stars else 0,
                    'Total Dest %': atk.total_dest,
                    'Avg Dest %': round(atk.avg_dest, 2) if atk.avg_dest else 0
                })

            # Buat File CSV Buffer
            file_buffer = self._generate_csv(csv_data)
            discord_file = discord.File(fp=file_buffer, filename=f"Rekap_CWL_{clan_tag.replace('#', '')}.csv")

            # Embed Ringkasan Top 5
            embed = discord.Embed(
                title=f"🏆 Laporan Akumulasi CWL — {clan_tag}",
                description=f"Total Perang CWL Tercatat: **{len(cwl_wars)} War**\nFile lengkap terlampir dalam format **CSV / Excel**.",
                color=discord.Color.gold()
            )
            
            top_5_str = ""
            for item in csv_data[:5]:
                top_5_str += f"**#{item['Rank']} {item['Nama Member']}** — ⭐️ {item['Total Stars']} Stars | 💥 {item['Avg Dest %']}% Avg Dest\n"
            
            embed.add_field(name="🥇 Top 5 Leaderboard CWL", value=top_5_str or "Kosong", inline=False)
            embed.set_footer(text="Niki CoC Bot — VIP Analytics")

            await interaction.followup.send(embed=embed, file=discord_file)

        except Exception as e:
            db.rollback()
            await interaction.followup.send(f"❌ Terjadi kesalahan saat memproses data: {e}")
        finally:
            db.close()

    @app_commands.command(name="rekap-war", description="[VIP] Rekap akumulasi performa War Biasa bulanan (Export CSV)")
    async def rekap_war(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild_id = str(interaction.guild_id)
        
        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == guild_id).first()
            if not config or not config.clan_tag:
                return await interaction.followup.send("❌ Server belum di-setup! Gunakan `/setup` terlebih dahulu.")

            tier_status = str(config.tier).lower() if config.tier else "free"
            if tier_status not in ["pro", "ai_pro"]:
                return await interaction.followup.send(
                    "⚠️ **Fitur VIP Exclusive**\n"
                    "Ekspor Laporan Akumulasi War Biasa (CSV) khusus untuk **VIP Supporter**.\n"
                    "Hubungi Admin untuk upgrade lisensi server kamu!"
                )

            clan_tag = config.clan_tag
            
            # Ambil War Biasa (bukan CWL)
            normal_wars = db.query(War).filter(
                War.clan_tag == clan_tag,
                War.is_cwl == False
            ).all()

            if not normal_wars:
                return await interaction.followup.send(f"❌ Belum ada data akumulasi War Biasa di database untuk clan `{clan_tag}`.")

            war_ids = [w.id for w in normal_wars]

            attacks = db.query(
                WarAttack.attacker_name,
                WarAttack.attacker_tag,
                func.count(WarAttack.id).label('total_attacks'),
                func.sum(WarAttack.stars).label('total_stars'),
                func.avg(WarAttack.stars).label('avg_stars'),
                func.sum(WarAttack.destruction_percentage).label('total_dest'),
                func.avg(WarAttack.destruction_percentage).label('avg_dest')
            ).filter(WarAttack.war_id.in_(war_ids))\
             .group_by(WarAttack.attacker_name, WarAttack.attacker_tag)\
             .order_by(func.sum(WarAttack.stars).desc(), func.avg(WarAttack.destruction_percentage).desc())\
             .all()

            if not attacks:
                return await interaction.followup.send("❌ Belum ada histori serangan war biasa yang tercatat.")

            csv_data = []
            for idx, atk in enumerate(attacks, 1):
                csv_data.append({
                    'Rank': idx,
                    'Nama Member': atk.attacker_name,
                    'Tag Member': atk.attacker_tag,
                    'Total Attack': atk.total_attacks,
                    'Total Stars': atk.total_stars,
                    'Avg Stars': round(atk.avg_stars, 2) if atk.avg_stars else 0,
                    'Total Dest %': atk.total_dest,
                    'Avg Dest %': round(atk.avg_dest, 2) if atk.avg_dest else 0
                })

            file_buffer = self._generate_csv(csv_data)
            discord_file = discord.File(fp=file_buffer, filename=f"Rekap_War_{clan_tag.replace('#', '')}.csv")

            embed = discord.Embed(
                title=f"⚔️ Laporan Akumulasi War Biasa — {clan_tag}",
                description=f"Total Perang Tercatat: **{len(normal_wars)} War**\nFile lengkap terlampir dalam format **CSV / Excel**.",
                color=discord.Color.blue()
            )
            
            top_5_str = ""
            for item in csv_data[:5]:
                top_5_str += f"**#{item['Rank']} {item['Nama Member']}** — ⭐️ {item['Total Stars']} Stars | 💥 {item['Avg Dest %']}% Avg Dest\n"
            
            embed.add_field(name="🥇 Top 5 Leaderboard War", value=top_5_str or "Kosong", inline=False)
            embed.set_footer(text="Niki CoC Bot — VIP Analytics")

            await interaction.followup.send(embed=embed, file=discord_file)

        except Exception as e:
            db.rollback()
            await interaction.followup.send(f"❌ Terjadi kesalahan saat memproses data: {e}")
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(RecapCommands(bot))
