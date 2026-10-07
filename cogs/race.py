import discord
from discord import app_commands
from discord.ext import commands
from services.db import get_db, check_standar_access
from services.coc_client import CoCClient
from models import ServerConfig, CWLSeason, RaceReward, War, WarAttack
from sqlalchemy import text, func
from datetime import datetime

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

    @app_commands.command(name="racecwl", description="[STANDAR] Live Ranking & Kandidat Bonus CWL Terbaik Saat Ini")
    async def race_cwl(self, interaction: discord.Interaction):
        await interaction.response.defer()

        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")

        # Tarik data live grup CWL langsung dari API Clash of Clans
        cwl_data = await self.coc.get_cwl_group(clan_tag)
        if not cwl_data or not isinstance(cwl_data, dict) or cwl_data.get('state') == 'notInWar':
            return await interaction.followup.send("🛡️ Clan tidak sedang dalam masa Clan War League (CWL).")

        season = cwl_data.get('season', 'Unknown')
        rounds = cwl_data.get('rounds', [])

        players = {}
        active_rounds = 0

        for r in rounds:
            war_tags = r.get('warTags', [])
            round_counted = False
            for w_tag in war_tags:
                if w_tag == '#0': continue
                cwl_war = await self.coc.get_cwl_war(w_tag)
                
                # Ambil data dari ronde yang sedang berjalan atau sudah selesai
                if cwl_war and isinstance(cwl_war, dict) and cwl_war.get('state') in ['inWar', 'warEnded']:
                    our_clan = None
                    if cwl_war.get('clan', {}).get('tag') == clan_tag:
                        our_clan = cwl_war.get('clan')
                    elif cwl_war.get('opponent', {}).get('tag') == clan_tag:
                        our_clan = cwl_war.get('opponent')
                        
                    if our_clan:
                        round_counted = True
                        for member in our_clan.get('members', []):
                            m_tag = member.get('tag')
                            m_name = member.get('name', 'Unknown')
                            
                            if m_tag not in players:
                                players[m_tag] = {'name': m_name, 'tag': m_tag, 'stars': 0, 'dest': 0.0, 'attacks': 0}
                            
                            for atk in member.get('attacks', []):
                                players[m_tag]['stars'] += atk.get('stars', 0)
                                players[m_tag]['dest'] += atk.get('destructionPercentage', 0.0)
                                players[m_tag]['attacks'] += 1
                                
            if round_counted:
                active_rounds += 1

        if not players:
            return await interaction.followup.send("❌ Belum ada data serangan CWL yang tercatat di API untuk musim ini.")

        # Urutkan berdasarkan: 1. Bintang Tertinggi, 2. Total Destruksi Tertinggi
        sorted_players = sorted(
            players.values(),
            key=lambda x: (x['stars'], x['dest']),
            reverse=True
        )

        embed = discord.Embed(
            title=f"🏆 Live Kandidat Bonus CWL ({season})",
            description=f"Status Ronde: **Round Berjalan {active_rounds}/{len(rounds)}**\n*Diurutkan otomatis dari Bintang terbanyak & Destruksi tertinggi (Referensi Utama Peraih Medali Bonus).*",
            color=discord.Color.purple()
        )

        leaderboard_text = ""
        # Tampilkan Top 10 Kandidat Terbaik
        for i, p in enumerate(sorted_players[:10], 1):
            badge = "🎁 " if i <= 8 else "" # Anggap slot bonus standar sekitar 8 orang (bisa disesuaikan)
            leaderboard_text += f"{i}. {badge}**{p['name']}**\n└ ⚔️ Atk: {p['attacks']} | ⭐ Bintang: {p['stars']} |  destrucción: {p['dest']:.1f}%\n"

        embed.add_field(name="📊 Top 10 Performa Member", value=leaderboard_text if leaderboard_text else "Belum ada data.", inline=False)
        embed.set_footer(text="ixiera.id — Operating System Studio | WA: https://wa.me/6285736048626")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="givereward", description="[STANDAR] Catat reward/bonus ke member tertentu")
    @app_commands.describe(
        scope="Pilih kategori (War Classic atau CWL Musim Ini)",
        nama_member="Nama member sesuai di game",
        catatan="Catatan (Contoh: Medali CWL + Gold Pass)"
    )
    @app_commands.choices(scope=[
        app_commands.Choice(name="War Classic", value="war"),
        app_commands.Choice(name="CWL Musim Ini", value="cwl")
    ])
    async def give_reward(
        self, 
        interaction: discord.Interaction, 
        scope: app_commands.Choice[str],
        nama_member: str,
        catatan: str
    ):
        await interaction.response.defer(ephemeral=True)
        
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg, ephemeral=True)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!", ephemeral=True)

        scope_type = scope.value
        
        clan_data = await self.coc.get_clan_info(clan_tag)
        if not clan_data or 'memberList' not in clan_data:
            return await interaction.followup.send("❌ Gagal mengambil data clan dari API.", ephemeral=True)

        target = next((m for m in clan_data['memberList'] if nama_member.lower() in m.get('name', '').lower()), None)
        if not target:
            return await interaction.followup.send(f"❌ Member dengan nama `{nama_member}` tidak ditemukan di clan.", ephemeral=True)

        db = get_db()
        try:
            scope_id = 0
            if scope_type == 'cwl':
                current_month = datetime.now().strftime('%Y-%m')
                cwl = db.query(CWLSeason).filter(CWLSeason.clan_tag == clan_tag, CWLSeason.month == current_month).first()
                if cwl: scope_id = cwl.id
            else:
                w = db.query(War).filter(War.clan_tag == clan_tag, War.is_cwl == False).order_by(War.id.desc()).first()
                if w: scope_id = w.id

            reward = RaceReward(
                scope_type=scope_type,
                scope_id=scope_id,
                player_tag=target.get('tag'),
                reward_note=f"[{interaction.user.name}] {catatan}"
            )
            db.add(reward)
            db.commit()

            await interaction.followup.send(
                f"✅ Berhasil mencatat reward untuk **{target.get('name')}** (`{target.get('tag')}`)!\n📝 **Catatan:** {catatan}",
                ephemeral=True
            )
        except Exception as e:
            db.rollback()
            await interaction.followup.send(f"❌ Gagal menyimpan reward: {e}", ephemeral=True)
        finally:
            db.close()

    @app_commands.command(name="rewardhistory", description="[STANDAR] Lihat riwayat pemberian reward ke member")
    async def reward_history(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg, ephemeral=True)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!", ephemeral=True)

        db = get_db()
        try:
            history = db.query(RaceReward).order_by(RaceReward.id.desc()).limit(10).all()

            embed = discord.Embed(title="📜 Riwayat Pemberian Reward", color=discord.Color.blue())

            if not history:
                embed.description = "Belum ada riwayat reward yang dicatat."
            else:
                for h in history:
                    date_str = h.claimed_at.strftime("%d %b %Y") if hasattr(h, 'claimed_at') and h.claimed_at else "-"
                    embed.add_field(
                        name=f"🎁 Tag: {h.player_tag} ({h.scope_type.upper()})",
                        value=f"• Catatan: {h.reward_note}\n• Tanggal: {date_str}",
                        inline=False
                    )

            embed.set_footer(text="ixiera.id — Operating System Studio | WA: https://wa.me/6285736048626")
            await interaction.followup.send(embed=embed, ephemeral=True)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(RaceCommands(bot))
