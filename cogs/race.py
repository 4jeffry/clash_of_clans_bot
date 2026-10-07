import discord
from discord import app_commands
from discord.ext import commands
from services.db import get_db, check_standar_access
from services.coc_client import CoCClient
from models import ServerConfig, CWLSeason, RaceReward, War, WarAttack
from sqlalchemy import text, func
from datetime import datetime

class RewardSelectView(discord.ui.View):
    def __init__(self, top_members, scope_type="war"):
        super().__init__(timeout=60)
        self.scope_type = scope_type
        
        options = []
        for m in top_members:
            options.append(
                discord.SelectOption(
                    label=m['name'][:25], 
                    value=m['tag'], 
                    description=f"Skor: {int(m['stars'])}⭐ | Destruksi: {m['dest']:.1f}%"
                )
            )
        self.add_item(RewardSelect(options, scope_type))

class RewardSelect(discord.ui.Select):
    def __init__(self, options, scope_type):
        super().__init__(placeholder="Pilih kandidat prioritas peraih bonus...", min_values=1, max_values=1, options=options)
        self.scope_type = scope_type

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RewardNoteModal(player_tag=self.values[0], scope_type=self.scope_type))

class RewardNoteModal(discord.ui.Modal, title="Form Catatan Apresiasi Member"):
    keterangan = discord.ui.TextInput(
        label="Keterangan / Alasan Reward",
        style=discord.TextStyle.paragraph,
        placeholder="Contoh: MVP Rekap bulan ini karena konsisten sumbang bintang tertinggi!",
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
        self.coc = CoCClient()

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
        # Karena kita melakukan kalkulasi API yang butuh waktu, pakai ephemeral defer
        await interaction.response.defer(ephemeral=True)
        
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg, ephemeral=True)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!", ephemeral=True)

        scope_type = scope.value
        top_members = []

        if scope_type == "cwl":
            # ==========================================
            # LIVE API FETCH KHUSUS CWL (BYPASS DATABASE)
            # ==========================================
            cwl_data = await self.coc.get_cwl_group(clan_tag)
            if not cwl_data or cwl_data.get('state') == 'notInWar':
                return await interaction.followup.send("🛡️ Clan tidak sedang dalam masa CWL.", ephemeral=True)
                
            players = {}
            for r in cwl_data.get('rounds', []):
                for w_tag in r.get('warTags', []):
                    if w_tag == '#0': continue
                    cwl_war = await self.coc.get_cwl_war(w_tag)
                    if cwl_war and cwl_war.get('state') in ['inWar', 'warEnded']:
                        our_clan = None
                        if cwl_war.get('clan', {}).get('tag') == clan_tag:
                            our_clan = cwl_war.get('clan')
                        elif cwl_war.get('opponent', {}).get('tag') == clan_tag:
                            our_clan = cwl_war.get('opponent')
                        
                        if our_clan:
                            for member in our_clan.get('members', []):
                                m_tag = member.get('tag')
                                if m_tag not in players:
                                    players[m_tag] = {'name': member.get('name', 'Unknown'), 'tag': m_tag, 'stars': 0, 'dest': 0.0}
                                for atk in member.get('attacks', []):
                                    players[m_tag]['stars'] += atk.get('stars', 0)
                                    players[m_tag]['dest'] += atk.get('destructionPercentage', 0.0)
            
            # Sortir by Bintang Tertinggi -> Destruksi Tertinggi
            top_members = sorted(players.values(), key=lambda x: (x['stars'], x['dest']), reverse=True)[:5]
        else:
            # ==========================================
            # DATABASE FETCH KHUSUS WAR CLASSIC
            # ==========================================
            db = get_db()
            try:
                latest_war = db.query(War).filter(War.clan_tag == clan_tag, War.is_cwl == False).order_by(War.id.desc()).first()
                if latest_war:
                    top = db.query(
                        WarAttack.attacker_name,
                        WarAttack.attacker_tag,
                        func.sum(WarAttack.stars).label('stars'),
                        func.sum(WarAttack.destruction_percentage).label('dest')
                    ).filter(WarAttack.war_id == latest_war.id)\
                     .group_by(WarAttack.attacker_name, WarAttack.attacker_tag)\
                     .order_by(func.sum(WarAttack.stars).desc(), func.sum(WarAttack.destruction_percentage).desc())\
                     .limit(5).all()
                    
                    top_members = [{'name': m.attacker_name, 'tag': m.attacker_tag, 'stars': m.stars, 'dest': m.dest} for m in top]
            finally:
                db.close()

        if not top_members:
            return await interaction.followup.send(f"❌ Belum ada data rekap untuk **{scope.name}**.", ephemeral=True)

        view = RewardSelectView(top_members=top_members, scope_type=scope_type)
        await interaction.followup.send(
            f"🎁 **Pilih Kandidat Prioritas Bonus** dari rekap **{scope.name}**:\n*Kandidat otomatis diurutkan berdasarkan perolehan Stars tertinggi, lalu Total Destruksi jika Stars seri.*",
            view=view,
            ephemeral=True
        )

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
