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
        """Helper cerdas: Cek War Biasa dulu, kalau tidak ada baru fallback cek CWL Ronde Aktif"""
        war_data = await self.coc.get_current_war(clan_tag)
        if war_data and war_data.get('state') in ['inWar', 'preparation']:
            return war_data, "REGULAR"

        # Cek CWL Group jika War Biasa notInWar
        cwl_group = await self.coc.get_cwl_group(clan_tag)
        if cwl_group and cwl_group.get('state') != 'notInWar':
            rounds = cwl_group.get('rounds', [])
            for r in reversed(rounds):
                war_tags = r.get('warTags', [])
                for w_tag in war_tags:
                    if w_tag == '#0': continue
                    cwl_war = await self.coc.get_cwl_war(w_tag)
                    if cwl_war and (cwl_war.get('clan', {}).get('tag') == clan_tag or cwl_war.get('opponent', {}).get('tag') == clan_tag):
                        if cwl_war.get('state') in ['inWar', 'preparation']:
                            # Sesuaikan posisi clan agar clan kita selalu di sebelah kiri
                            if cwl_war.get('opponent', {}).get('tag') == clan_tag:
                                cwl_war['clan'], cwl_war['opponent'] = cwl_war['opponent'], cwl_war['clan']
                            return cwl_war, "CWL"

        return war_data, "REGULAR"

    @app_commands.command(name="cwl", description="Cek status & grup Clan War League (CWL) saat ini")
    async def cwl_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")
        
        cwl_data = await self.coc.get_cwl_group(clan_tag)
        if not cwl_data or cwl_data.get('state') == 'notInWar':
            return await interaction.followup.send("🛡️ Clan tidak sedang dalam masa Clan War League (CWL).")
        
        state = cwl_data.get('state', 'Unknown')
        season = cwl_data.get('season', 'Unknown')
        clans = cwl_data.get('clans', [])
        
        embed = discord.Embed(title=f"🏆 Clan War League: Musim {season}", color=discord.Color.purple())
        embed.add_field(name="Status", value=f"`{state.capitalize()}`", inline=False)
        
        clan_names = [c.get('name') for c in clans]
        if clan_names:
            formatted_clans = "\n".join([f"{i}. {name}" for i, name in enumerate(clan_names, 1)])
            embed.add_field(name="Grup CWL (8 Clan)", value=f"```text\n{formatted_clans}\n```", inline=False)
            
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="warstatus", description="Melihat status Clan War / CWL saat ini")
    async def warstatus(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server ini belum di-setup!")
        
        war_data, war_type = await self._get_active_war(clan_tag)
        if not war_data or war_data.get('state') == 'notInWar':
            return await interaction.followup.send("🛡️ Clan sedang tidak dalam perang aktif atau masa persiapan awal.")
        
        state = war_data.get('state', 'unknown').upper()
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

        # Format Tampilan Monospace / Codeblock Box
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
        if not war_data or war_data.get('state') != 'inWar':
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
