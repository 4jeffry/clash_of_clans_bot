import discord
from discord import app_commands
from discord.ext import commands
from services.db import get_db, check_standar_access
from models import ServerConfig, CWLSeason, RaceReward, War, WarAttack
from sqlalchemy import text
from datetime import datetime

class RaceCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_clan_tag(self, guild_id):
        db = get_db()
        try:
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(guild_id)).first()
            return config.clan_tag if config else None
        finally:
            db.close()

    @app_commands.command(name="racewar", description="[STANDAR] Leaderboard stars perang aktif / perang terakhir")
    async def race_war(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")

        db = get_db()
        try:
            query_war = text("""
                SELECT id, opponent_name, state FROM wars 
                WHERE clan_tag = :clan_tag AND cwl_season_id IS NULL
                ORDER BY id DESC LIMIT 1
            """)
            war = db.execute(query_war, {"clan_tag": clan_tag}).mappings().first()

            if not war:
                return await interaction.followup.send("🛡️ Belum ada data War Classic yang tersimpan di database.")

            query_rank = text("""
                SELECT attacker_tag, attacker_name, SUM(stars) as total_stars, COUNT(id) as total_attacks
                FROM war_attacks
                WHERE war_id = :war_id
                GROUP BY attacker_tag, attacker_name
                ORDER BY total_stars DESC, total_attacks ASC
            """)
            rankings = db.execute(query_rank, {"war_id": war['id']}).mappings().all()

            rewards = db.query(RaceReward).filter(
                RaceReward.scope_type == 'war',
                RaceReward.scope_id == war['id']
            ).all()
            rewarded_tags = [r.player_tag for r in rewards]

            embed = discord.Embed(
                title=f"🏁 Race War Classic vs {war['opponent_name']}",
                description=f"Status Perang: **{str(war['state']).capitalize()}**",
                color=discord.Color.gold()
            )

            if not rankings:
                embed.description += "\n\n*Belum ada data serangan tercatat.*"
            else:
                leaderboard_text = ""
                for i, r in enumerate(rankings, 1):
                    badge = "🎁 " if r['attacker_tag'] in rewarded_tags else ""
                    leaderboard_text += f"{i}. {badge}**{r['attacker_name']}** — ⭐ {r['total_stars']} Stars ({r['total_attacks']} Attack)\n"
                embed.add_field(name="🏆 Klasemen Bintang Member", value=leaderboard_text, inline=False)

            embed.set_footer(text="ixiera.id — Operating System Studio | WA: https://wa.me/6285736048626")
            await interaction.followup.send(embed=embed)
        finally:
            db.close()

    @app_commands.command(name="racecwl", description="[STANDAR] Ranking akumulasi stars CWL musim berjalan")
    async def race_cwl(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")

        current_month = datetime.now().strftime('%Y-%m')
        db = get_db()
        try:
            cwl = db.query(CWLSeason).filter(
                CWLSeason.clan_tag == clan_tag,
                CWLSeason.month == current_month
            ).first()

            if not cwl:
                return await interaction.followup.send(f"🛡️ Belum ada data CWL tersimpan untuk musim **{current_month}**.")

            query_cwl_rank = text("""
                SELECT wa.attacker_tag, wa.attacker_name, SUM(wa.stars) as total_stars, COUNT(wa.id) as total_attacks
                FROM war_attacks wa
                JOIN wars w ON wa.war_id = w.id
                WHERE w.cwl_season_id = :season_id
                GROUP BY wa.attacker_tag, wa.attacker_name
                ORDER BY total_stars DESC, total_attacks ASC
            """)
            rankings = db.execute(query_cwl_rank, {"season_id": cwl.id}).mappings().all()

            rewards = db.query(RaceReward).filter(
                RaceReward.scope_type == 'cwl',
                RaceReward.scope_id == cwl.id
            ).all()
            rewarded_tags = [r.player_tag for r in rewards]

            embed = discord.Embed(
                title=f"🏆 CWL Season Race — Musim {current_month}",
                description="Akumulasi Stars dari seluruh ronde CWL bulan ini:",
                color=discord.Color.purple()
            )

            if not rankings:
                embed.description += "\n\n*Belum ada data serangan tercatat.*"
            else:
                leaderboard_text = ""
                for i, r in enumerate(rankings, 1):
                    badge = "🎁 " if r['attacker_tag'] in rewarded_tags else ""
                    leaderboard_text += f"{i}. {badge}**{r['attacker_name']}** — ⭐ {r['total_stars']} Stars ({r['total_attacks']} Attack)\n"
                embed.add_field(name="📊 Klasemen Akumulasi CWL", value=leaderboard_text, inline=False)

            embed.set_footer(text="ixiera.id — Operating System Studio | WA: https://wa.me/6285736048626")
            await interaction.followup.send(embed=embed)
        finally:
            db.close()

    @app_commands.command(name="givereward", description="[STANDAR] Tandai pemberian reward untuk member")
    @app_commands.choices(scope=[
        app_commands.Choice(name="War Classic Terakhir", value="war"),
        app_commands.Choice(name="CWL Musim Ini", value="cwl")
    ])
    async def give_reward(
        self, 
        interaction: discord.Interaction, 
        scope: app_commands.Choice[str], 
        nama_member: str, 
        catatan: str = None
    ):
        await interaction.response.defer()
        
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")

        db = get_db()
        try:
            scope_type = scope.value
            scope_id = None

            if scope_type == 'war':
                query_war = text("SELECT id FROM wars WHERE clan_tag = :clan_tag AND cwl_season_id IS NULL ORDER BY id DESC LIMIT 1")
                war = db.execute(query_war, {"clan_tag": clan_tag}).mappings().first()
                if not war:
                    return await interaction.followup.send("❌ Tidak ada War Classic aktif/terakhir di database.")
                scope_id = war['id']
            else:
                current_month = datetime.now().strftime('%Y-%m')
                cwl = db.query(CWLSeason).filter(CWLSeason.clan_tag == clan_tag, CWLSeason.month == current_month).first()
                if not cwl:
                    return await interaction.followup.send("❌ CWL musim bulan ini belum tersimpan di database.")
                scope_id = cwl.id

            query_player = text("""
                SELECT attacker_tag, attacker_name FROM war_attacks 
                WHERE LOWER(attacker_name) LIKE :name 
                ORDER BY id DESC LIMIT 1
            """)
            player = db.execute(query_player, {"name": f"%{nama_member.lower()}%"}).mappings().first()

            if not player:
                return await interaction.followup.send(f"❌ Member `{nama_member}` tidak ditemukan dalam catatan serangan perang.")

            target_tag = player['attacker_tag']
            actual_name = player['attacker_name']

            existing = db.query(RaceReward).filter(
                RaceReward.scope_type == scope_type,
                RaceReward.scope_id == scope_id,
                RaceReward.player_tag == target_tag
            ).first()

            if existing:
                return await interaction.followup.send(
                    f"⚠️ **{actual_name}** sudah pernah diberi reward untuk event ini pada {existing.claimed_at.strftime('%d/%m/%Y %H:%M')}!"
                )

            new_reward = RaceReward(
                scope_type=scope_type,
                scope_id=scope_id,
                player_tag=target_tag,
                reward_note=catatan or "Reward Pembinaan / MVP"
            )
            db.add(new_reward)
            db.commit()

            embed = discord.Embed(
                title="🎁 Reward Berhasil Dicatat!",
                description=f"Reward untuk **{actual_name}** pada event **{scope.name}** telah resmi tersimpan.",
                color=discord.Color.green()
            )
            embed.add_field(name="Catatan Reward", value=catatan or "-", inline=False)
            embed.set_footer(text="ixiera.id — Operating System Studio | WA: https://wa.me/6285736048626")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            db.rollback()
            await interaction.followup.send("❌ Gagal menyimpan reward ke database.")
        finally:
            db.close()

    @app_commands.command(name="rewardhistory", description="[STANDAR] Lihat riwayat pemberian reward ke member")
    async def reward_history(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")

        db = get_db()
        try:
            query_history = text("""
                SELECT rr.scope_type, rr.reward_note, rr.claimed_at, wa.attacker_name
                FROM race_rewards rr
                LEFT JOIN (
                    SELECT DISTINCT attacker_tag, attacker_name FROM war_attacks
                ) wa ON rr.player_tag = wa.attacker_tag
                ORDER BY rr.id DESC LIMIT 10
            """)
            history = db.execute(query_history).mappings().all()

            embed = discord.Embed(title="📜 Riwayat Pemberian Reward", color=discord.Color.blue())

            if not history:
                embed.description = "Belum ada riwayat reward yang dicatat."
            else:
                for h in history:
                    name = h['attacker_name'] or "Member"
                    date_str = h['claimed_at'].strftime("%d %b %Y")
                    embed.add_field(
                        name=f"🎁 {name} ({h['scope_type'].upper()})",
                        value=f"• Catatan: {h['reward_note']}\n• Tanggal: {date_str}",
                        inline=False
                    )

            embed.set_footer(text="ixiera.id — Operating System Studio | WA: https://wa.me/6285736048626")
            await interaction.followup.send(embed=embed)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(RaceCommands(bot))
