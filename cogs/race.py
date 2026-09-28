import discord
from discord import app_commands
from discord.ext import commands
from services.db import get_db, check_standar_access
from models import ServerConfig, CWLSeason, RaceReward, War, WarAttack
from sqlalchemy import text, func
from datetime import datetime

class RewardSelectView(discord.ui.View):
    def __init__(self, db_session, clan_tag, scope_type="war"):
        super().__init__(timeout=60)
        self.db = db_session
        self.clan_tag = clan_tag
        self.scope_type = scope_type
        
        # Ambil Top 5 member berdasarkan akumulasi rekap (War Classic terakhir atau CWL musim ini)
        if scope_type == "cwl":
            current_month = datetime.now().strftime('%Y-%m')
            season = self.db.query(CWLSeason).filter(CWLSeason.clan_tag == clan_tag, CWLSeason.month == current_month).first()
            if season:
                cwl_wars = self.db.query(War).filter(War.cwl_season_id == season.id).all()
                war_ids = [w.id for w in cwl_wars]
                if war_ids:
                    top_members = self.db.query(
                        WarAttack.attacker_name,
                        WarAttack.attacker_tag,
                        func.sum(WarAttack.stars).label('stars')
                    ).filter(WarAttack.war_id.in_(war_ids))\
                     .group_by(WarAttack.attacker_name, WarAttack.attacker_tag)\
                     .order_by(func.sum(WarAttack.stars).desc())\
                     .limit(5).all()
                else:
                    top_members = []
            else:
                top_members = []
        else:
            # War Classic Terakhir / Akumulasi
            latest_war = self.db.query(War).filter(War.clan_tag == clan_tag, War.is_cwl == False).order_by(War.id.desc()).first()
            if latest_war:
                top_members = self.db.query(
                    WarAttack.attacker_name,
                    WarAttack.attacker_tag,
                    func.sum(WarAttack.stars).label('stars')
                ).filter(WarAttack.war_id == latest_war.id)\
                 .group_by(WarAttack.attacker_name, WarAttack.attacker_tag)\
                 .order_by(func.sum(WarAttack.stars).desc())\
                 .limit(5).all()
            else:
                top_members = []
        
        if top_members:
            options = [
                discord.SelectOption(
                    label=m.attacker_name[:25], 
                    value=m.attacker_tag, 
                    description=f"Total Bintang Rekap: {m.stars}⭐"
                ) for m in top_members
            ]
            self.add_item(RewardSelect(options, scope_type))

class RewardSelect(discord.ui.Select):
    def __init__(self, options, scope_type):
        super().__init__(placeholder="Pilih kandidat top dari rekap...", min_values=1, max_values=1, options=options)
        self.scope_type = scope_type

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RewardNoteModal(player_tag=self.values[0], scope_type=self.scope_type))

class RewardNoteModal(discord.ui.Modal, title="Form Catatan Apresiasi Member"):
    keterangan = discord.ui.TextInput(
        label="Keterangan / Alasan Reward",
        style=discord.TextStyle.paragraph,
        placeholder="Contoh: MVP Rekap karena konsisten sumbang bintang tertinggi!",
        required=True,
        max_length=300
    )

    def __init__(self, player_tag: str, scope_type: str = "war"):
        super().__init__()
        self.player_tag = player_tag
        self.scope_type = scope_type

    async def on_submit(self, interaction: discord.Interaction):
        db = get_db()
        try:
            # Ambil ID scope yang sesuai (war terakhir atau cwl aktif)
            config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(interaction.guild_id)).first()
            clan_tag = config.clan_tag if config else None
            
            scope_id = 0
            if clan_tag:
                if self.scope_type == 'cwl':
                    current_month = datetime.now().strftime('%Y-%m')
                    cwl = db.query(CWLSeason).filter(CWLSeason.clan_tag == clan_tag, CWLSeason.month == current_month).first()
                    if cwl: scope_id = cwl.id
                else:
                    w = db.query(War).filter(War.clan_tag == clan_tag, War.is_cwl == False).order_by(War.id.desc()).first()
                    if w: scope_id = w.id

            reward = RaceReward(
                scope_type=self.scope_type,
                scope_id=scope_id,
                player_tag=self.player_tag,
                reward_note=f"[{interaction.user.name}] {self.keterangan.value}"
            )
            db.add(reward)
            db.commit()

            await interaction.response.send_message(
                f"✅ Berhasil mencatat apresiasi untuk tag `{self.player_tag}` ({self.scope_type.upper()})!\n📝 **Nota:** {self.keterangan.value}",
                ephemeral=True
            )
        except Exception as e:
            db.rollback()
            await interaction.followup.send(f"❌ Gagal menyimpan reward: {e}", ephemeral=True)
        finally:
            db.close()


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

    @app_commands.command(name="racewar", description="[STANDAR] Leaderboard Offense & Defense perang aktif")
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
                WITH Offense AS (
                    SELECT attacker_tag as tag, attacker_name as name, SUM(stars) as atk_stars, COUNT(id) as atk_count
                    FROM war_attacks WHERE war_id = :war_id GROUP BY attacker_tag, attacker_name
                ),
                Defense AS (
                    SELECT defender_tag as tag, MAX(stars) as def_stars_given, MAX(destruction_percentage) as def_dest
                    FROM war_attacks WHERE war_id = :war_id GROUP BY defender_tag
                )
                SELECT o.tag, o.name, o.atk_stars, o.atk_count, 
                       COALESCE(d.def_stars_given, 0) as def_stars, 
                       COALESCE(d.def_dest, 0) as def_dest
                FROM Offense o
                LEFT JOIN Defense d ON o.tag = d.tag
                ORDER BY o.atk_stars DESC, def_stars ASC, o.atk_count ASC
            """)
            rankings = db.execute(query_rank, {"war_id": war['id']}).mappings().all()

            rewards = db.query(RaceReward).filter(
                RaceReward.scope_type == 'war',
                RaceReward.scope_id == war['id']
            ).all()
            rewarded_tags = [r.player_tag for r in rewards]

            embed = discord.Embed(
                title=f"🏁 Race War Classic vs {war['opponent_name']}",
                description=f"Status Perang: **{str(war['state']).capitalize()}**\n*(Diurutkan dari Bintang Serangan terbanyak & Pertahanan terkuat)*",
                color=discord.Color.gold()
            )

            if not rankings:
                embed.description += "\n\n*Belum ada data serangan tercatat.*"
            else:
                leaderboard_text = ""
                for i, r in enumerate(rankings[:15], 1):
                    badge = "🎁 " if r['tag'] in rewarded_tags else ""
                    def_status = f"🛡️ {r['def_stars']}⭐ ({r['def_dest']}%)" if r['def_stars'] > 0 else "🛡️ Aman"
                    leaderboard_text += f"{i}. {badge}**{r['name']}**\n└ ⚔️ {r['atk_stars']} Stars ({r['atk_count']} Atk) | {def_status}\n"
                embed.add_field(name="🏆 Klasemen Performa Member", value=leaderboard_text, inline=False)

            embed.set_footer(text="ixiera.id — Operating System Studio | WA: https://wa.me/6285736048626")
            await interaction.followup.send(embed=embed)
        finally:
            db.close()

    @app_commands.command(name="racecwl", description="[STANDAR] Ranking Offense & Defense CWL musim berjalan")
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
                WITH Offense AS (
                    SELECT wa.attacker_tag as tag, wa.attacker_name as name, SUM(wa.stars) as atk_stars, COUNT(wa.id) as atk_count
                    FROM war_attacks wa
                    JOIN wars w ON wa.war_id = w.id
                    WHERE w.cwl_season_id = :season_id
                    GROUP BY wa.attacker_tag, wa.attacker_name
                ),
                Defense AS (
                    SELECT wa.defender_tag as tag, SUM(wa.stars) as total_def_stars_given, AVG(wa.destruction_percentage) as avg_def_dest
                    FROM war_attacks wa
                    JOIN wars w ON wa.war_id = w.id
                    WHERE w.cwl_season_id = :season_id
                    GROUP BY wa.defender_tag
                )
                SELECT o.tag, o.name, o.atk_stars, o.atk_count, 
                       COALESCE(d.total_def_stars_given, 0) as def_stars, 
                       COALESCE(d.avg_def_dest, 0) as def_dest
                FROM Offense o
                LEFT JOIN Defense d ON o.tag = d.tag
                ORDER BY o.atk_stars DESC, def_stars ASC, o.atk_count ASC
            """)
            rankings = db.execute(query_cwl_rank, {"season_id": cwl.id}).mappings().all()

            rewards = db.query(RaceReward).filter(
                RaceReward.scope_type == 'cwl',
                RaceReward.scope_id == cwl.id
            ).all()
            rewarded_tags = [r.player_tag for r in rewards]

            embed = discord.Embed(
                title=f"🏆 CWL Season Race — Musim {current_month}",
                description="Akumulasi Performa (Serangan & Pertahanan) bulan ini:",
                color=discord.Color.purple()
            )

            if not rankings:
                embed.description += "\n\n*Belum ada data serangan tercatat.*"
            else:
                leaderboard_text = ""
                for i, r in enumerate(rankings[:15], 1):
                    badge = "🎁 " if r['tag'] in rewarded_tags else ""
                    avg_dest = round(r['def_dest'], 1)
                    def_status = f"🛡️ -{r['def_stars']}⭐ ({avg_dest}%)" if r['def_stars'] > 0 else "🛡️ Tembok Beton"
                    leaderboard_text += f"{i}. {badge}**{r['name']}**\n└ ⚔️ {r['atk_stars']} Stars ({r['atk_count']} Atk) | {def_status}\n"
                embed.add_field(name="📊 Klasemen Akumulasi CWL", value=leaderboard_text, inline=False)

            embed.set_footer(text="ixiera.id — Operating System Studio | WA: https://wa.me/6285736048626")
            await interaction.followup.send(embed=embed)
        finally:
            db.close()

    @app_commands.command(name="givereward", description="[STANDAR] Tandai pemberian reward untuk member berdasarkan rekap")
    @app_commands.choices(scope=[
        app_commands.Choice(name="War Classic (Rekap 30 Hari)", value="war"),
        app_commands.Choice(name="CWL Musim Ini (Semua Round)", value="cwl")
    ])
    async def give_reward(
        self, 
        interaction: discord.Interaction, 
        scope: app_commands.Choice[str]
    ):
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.response.send_message("❌ Server belum di-setup!", ephemeral=True)

        db = get_db()
        try:
            scope_type = scope.value
            view = RewardSelectView(db, clan_tag, scope_type=scope_type)
            
            if not view.children:
                return await interaction.response.send_message(
                    f"❌ Belum ada data rekap untuk kategori **{scope.name}** di database.",
                    ephemeral=True
                )

            await interaction.response.send_message(
                f"🎁 **Pilih Kandidat Top Member** dari rekap **{scope.name}**:",
                view=view,
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Terjadi kesalahan: {e}", ephemeral=True)
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
