import discord
from discord import app_commands
from discord.ext import commands
from services.llm_client import (
    run_ai_audit, 
    run_war_strategy, 
    run_ai_screen, 
    run_ai_scout,
    run_ai_opponent,
    run_ai_report  # GANTI base-scan jadi ai-report
)
from services.coc_client import CoCClient
from services.db import get_db
from models import ServerConfig
import asyncio

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
            
    async def send_long_message(self, interaction: discord.Interaction, text: str):
        if len(text) <= 2000:
            await interaction.followup.send(text)
        else:
            chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
            for chunk in chunks:
                await interaction.followup.send(chunk)
                await asyncio.sleep(1)

    # Helper Pintar buat AI biar tau lagi War Biasa atau CWL
    async def _get_smart_war_data(self, clan_tag: str):
        try:
            war_data = await self.coc.get_current_war(clan_tag)
            if war_data and isinstance(war_data, dict) and war_data.get('state') in ['inWar', 'preparation']:
                return war_data
        except Exception:
            pass

        # Fallback Cek CWL Group
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

    @app_commands.command(name="ai-audit", description="[AI PRO] Deep audit kesehatan clan & evaluasi member")
    async def ai_audit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        result = await run_ai_audit(str(interaction.guild_id))
        await self.send_long_message(interaction, result)

    @app_commands.command(name="war-strategy", description="[AI PRO] Analisis agregat war saat ini & rotasi attack")
    async def ai_war_strategy(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")

        war_data = await self._get_smart_war_data(clan_tag)
        result = await run_war_strategy(str(interaction.guild_id), war_data)
        await self.send_long_message(interaction, result)

    @app_commands.command(name="ai-report", description="[AI PRO] Evaluasi performa member & MVP pasca-war selesai")
    async def ai_report(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")
            
        war_logs = await self.coc.get_war_log(clan_tag)
        if not war_logs or isinstance(war_logs, str):
            return await interaction.followup.send("❌ Gagal membaca history war log atau setelan log private.")

        # Ambil war log paling baru
        latest_war_log = war_logs[0] if war_logs else None
        
        result = await run_ai_report(str(interaction.guild_id), latest_war_log)
        await self.send_long_message(interaction, result)

    @app_commands.command(name="ai-screen", description="[AI PRO] Cek profil calon member sebelum di-acc join")
    @app_commands.describe(player_tag="Tag player calon member (contoh: #ABC1234)")
    async def ai_screen(self, interaction: discord.Interaction, player_tag: str):
        await interaction.response.defer()
        
        if not player_tag.startswith('#'):
            player_tag = f"#{player_tag}"
            
        player_data = await self.coc.get_player_info(player_tag)
        if not player_data or 'tag' not in player_data:
            return await interaction.followup.send("❌ Data player tidak ditemukan! Pastikan tag-nya benar.")

        result = await run_ai_screen(str(interaction.guild_id), player_data)
        await self.send_long_message(interaction, result)

    @app_commands.command(name="ai-scout", description="[AI PRO] Intel war lawan: cari base terlemah & strategi pembersihan")
    async def ai_scout(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup!")

        war_data = await self._get_smart_war_data(clan_tag)
        if not war_data or war_data.get('state') not in ['inWar', 'preparation']:
            return await interaction.followup.send("❌ Clan sedang tidak dalam periode War atau CWL aktif!")

        result = await run_ai_scout(str(interaction.guild_id), war_data)
        await self.send_long_message(interaction, result)

    @app_commands.command(name="ai-opponent", description="[AI PRO] Scouting klan lawan: estimasi peluang menang & kekuatan")
    async def ai_opponent(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clan_tag = self.get_clan_tag(interaction.guild_id)
        if not clan_tag:
            return await interaction.followup.send("❌ Server belum di-setup! Gunakan `/setup`.")

        war_data = await self._get_smart_war_data(clan_tag)
        if not war_data or war_data.get('state') not in ['inWar', 'preparation']:
            return await interaction.followup.send("❌ Clan sedang tidak dalam periode War atau CWL aktif!")

        result = await run_ai_opponent(str(interaction.guild_id), clan_tag, war_data)
        await self.send_long_message(interaction, result)

async def setup(bot):
    await bot.add_cog(AICog(bot))
