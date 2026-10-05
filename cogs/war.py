import discord
from discord import app_commands
from discord.ext import commands
from services.coc_client import CoCClient
from services.db import get_db, check_standar_access
from models import ServerConfig

def create_progress_bar(percentage: float, length: int = 12) -> str:
    """Helper untuk membuat visual progress bar teks"""
    try:
        percentage = float(percentage)
    except (ValueError, TypeError):
        percentage = 0.0
    filled = int((percentage / 100) * length)
    empty = length - filled
    return f"[{'█' * filled}{'░' * empty}] {percentage:.1f}%"

class WarCommands(commands.Cog):
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

    async def _get_active_war(self, clan_tag: str):
        """Helper cerdas: Cek War Biasa dulu, kalau tidak ada baru fallback cek CWL (Prioritas inWar)"""
        try:
            war_data = await self.coc.get_current_war(clan_tag)
            if war_data and isinstance(war_data, dict) and war_data.get('state') in ['inWar', 'preparation']:
                return war_data, "REGULAR"
        except Exception:
            war_data = None

        # Fallback Cek CWL Group
        try:
            cwl_group = await self.coc.get_cwl_group(clan_tag)
            if cwl_group and isinstance(cwl_group, dict) and cwl_group.get('state') != 'notInWar':
                rounds = cwl_group.get('rounds', [])
                prep_war = None
                
                for r in reversed(rounds):
                    war_tags = r.get('warTags', [])
                    for w_tag in war_tags:
                        if w_tag == '#0': continue
                        
                        cwl_war = await self.coc.get_cwl_war(w_tag)
                        if cwl_war and isinstance(cwl_war, dict):
                            clan_t = cwl_war.get('clan', {}).get('tag')
                            opp_t = cwl_war.get('opponent', {}).get('tag')
                            
                            if clan_t == clan_tag or opp_t == clan_tag:
                                if opp_t == clan_tag:
                                    cwl_war['clan'], cwl_war['opponent'] = cwl_war['opponent'], cwl_war['clan']
                                
                                state = cwl_war.get('state')
                                if state == 'inWar':
                                    return cwl_war, "CWL"
                                elif state == 'preparation' and not prep_war:
                                    prep_war = cwl_war
                
                if prep_war:
                    return prep_war, "CWL"

        except Exception:
            pass

        return None, "REGULAR"

    @app_commands.command(name="cwl", description="Melihat Klasemen Pintar & Proyeksi Bintang CWL Grup Saat Ini")
    async def cwl_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")
        
        cwl_data = await self.coc.get_cwl_group(clan_tag)
        if not cwl_data or not isinstance(cwl_data, dict) or cwl_data.get('state') == 'notInWar':
            return await interaction.followup.send("🛡️ Clan tidak sedang dalam masa Clan War League (CWL).")
        
        season = cwl_data.get('season', 'Unknown')
        clans = cwl_data.get('clans', [])
        rounds = cwl_data.get('rounds', [])

        standings = {}
        for c in clans:
            c_tag = c.get('tag')
            standings[c_tag] = {
                'name': c.get('name', 'Unknown'),
                'tag': c_tag,
                'stars': 0,
                'wins': 0,
                'destruction': 0.0
            }

        for r in rounds:
            war_tags = r.get('warTags', [])
            for w_tag in war_tags:
                if w_tag == '#0': continue
                cwl_war = await self.coc.get_cwl_war(w_tag)
                if cwl_war and isinstance(cwl_war, dict) and cwl_war.get('state') in ['inWar', 'warEnded']:
                    c1 = cwl_war.get('clan', {})
                    c2 = cwl_war.get('opponent', {})
                    
                    t1, t2 = c1.get('tag'), c2.get('tag')
                    s1, s2 = c1.get('stars', 0), c2.get('stars', 0)
                    d1, d2 = c1.get('destructionPercentage', 0.0), c2.get('destructionPercentage', 0.0)

                    if t1 in standings:
                        standings[t1]['stars'] += s1
                        standings[t1]['destruction'] += d1
                    if t2 in standings:
                        standings[t2]['stars'] += s2
                        standings[t2]['destruction'] += d2

                    if cwl_war.get('state') == 'warEnded':
                        if s1 > s2 or (s1 == s2 and d1 > d2):
                            if t1 in standings: standings[t1]['wins'] += 1
                        elif s2 > s1 or (s1 == s2 and d2 > d1):
                            if t2 in standings: standings[t2]['wins'] += 1

        sorted_standings = sorted(
            standings.values(),
            key=lambda x: (x['stars'] + (x['wins'] * 10), x['destruction']),
            reverse=True
        )

        table_lines = []
        for rank, c in enumerate(sorted_standings, 1):
            name = c['name']
            raw_stars = c['stars']
            wins = c['wins']
            total_score = raw_stars + (wins * 10)
            
            marker = " *" if c['tag'] == clan_tag else ""
            
            # Baris 1: Nama Klan
            table_lines.append(f"{rank}. {name}{marker}")
            # Baris 2: Indikator Angka (Diperpendek spasinya agar fit di HP)
            table_lines.append(f"   └ Bintang:{raw_stars} | Win:{wins} | Tot:{total_score}")

        table_content = "```text\n" + "\n".join(table_lines) + "\n```"

        embed = discord.Embed(
            title=f"🏆 KLASEMEN CWL ({season})",
            description="🟢 **Top 1-2:** Promosi | ⚪ **3-6:** Aman | 🔴 **7-8:** Degradasi\n*(Penanda `*` adalah klan Anda)*",
            color=discord.Color.purple()
        )
        embed.add_field(name="───────────", value=table_content, inline=False)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="warstatus", description="Melihat status Clan War / CWL saat ini")
    async def warstatus(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")
        
        war_data, war_type = await self._get_active_war(clan_tag)
        if not war_data or not isinstance(war_data, dict) or war_data.get('state') == 'notInWar':
            return await interaction.followup.send("🛡️ Clan sedang tidak dalam perang aktif atau masa persiapan awal (atau War Log diset Private).")
        
        state = str(war_data.get('state', 'unknown')).upper()
        team_size = war_data.get('teamSize', 0)
        attacks_per_member = war_data.get('attacksPerMember', 1 if war_type == "CWL" else 2)
        total_possible_attacks = team_size * attacks_per_member

        clan = war_data.get('clan', {})
        opponent = war_data.get('opponent', {})
        
        clan_name = clan.get('name', 'Clan Kita')
        opp_name = opponent.get('name', 'Lawan')

        clan_stars = clan.get('stars', 0)
        opp_stars = opponent.get('stars', 0)

        clan_dest = clan.get('destructionPercentage', 0.0)
        opp_dest = opponent.get('destructionPercentage', 0.0)

        clan_attacks = clan.get('attacks', 0)
        opp_attacks = opponent.get('attacks', 0)

        war_box = []
        war_box.append(f"⚔️ {clan_name[:14]} vs {opp_name[:14]}")
        war_box.append("──────────────────────────────────────────")
        war_box.append(f"⭐ Bintang  : {clan_stars:>3}  VS  {opp_stars:<3}")
        war_box.append(f"⚔️ Serangan : {clan_attacks:>3}/{total_possible_attacks:<2}  VS  {opp_attacks:>3}/{total_possible_attacks:<2}")
        war_box.append("──────────────────────────────────────────")
        war_box.append(f"🔥 Kehancuran {clan_name[:10]}:")
        war_box.append(f"   {create_progress_bar(clan_dest)}")
        war_box.append(f"🔥 Kehancuran {opp_name[:10]}:")
        war_box.append(f"   {create_progress_bar(opp_dest)}")

        box_content = "```text\n" + "\n".join(war_box) + "\n```"

        color_map = {
            'INWAR': discord.Color.red(),
            'PREPARATION': discord.Color.blue(),
            'WARENDED': discord.Color.dark_gray()
        }

        title_prefix = "🏆 CWL ROUND STATUS" if war_type == "CWL" else "⚔️ WAR STATUS"

        embed = discord.Embed(
            title=f"{title_prefix}: {state}",
            description=f"Format: **{team_size} vs {team_size}** ({'1 Attack/Member' if war_type == 'CWL' else '2 Attacks/Member'})\n*Update real-time dari API Clash of Clans*",
            color=color_map.get(state, discord.Color.gold())
        )
        embed.add_field(name="───────────", value=box_content, inline=False)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="wartime", description="Cek sisa waktu war & sisa attack yang belum dipakai")
    async def wartime(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        has_access, err_msg = check_standar_access(interaction.guild_id)
        if not has_access:
            return await interaction.followup.send(err_msg)

        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")

        war_data, war_type = await self._get_active_war(clan_tag)
        if not war_data or not isinstance(war_data, dict) or war_data.get('state') != 'inWar':
            return await interaction.followup.send("🛡️ Clan sedang tidak dalam masa perang aktif (inWar).")

        clan = war_data.get('clan', {})
        members = clan.get('members', [])
        
        total_attacks_used = sum(len(m.get('attacks', [])) for m in members)
        max_attacks = len(members) * war_data.get('attacksPerMember', 1 if war_type == "CWL" else 2)
        remaining_attacks = max_attacks - total_attacks_used

        embed = discord.Embed(title=f"⏰ WARTIME & ATTACK CHECK ({war_type})", color=discord.Color.dark_red())
        
        info_text = (
            f"```text\n"
            f"Sisa Attack Clan : {remaining_attacks} / {max_attacks}\n"
            f"Total Stars      : {clan.get('stars', 0)}\n"
            f"Total Destruksi  : {clan.get('destructionPercentage', 0):.1f}%\n"
            f"```"
        )
        embed.add_field(name="───────────", value=info_text, inline=False)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(WarCommands(bot))
