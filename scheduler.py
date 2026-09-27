import logging
import asyncio
from datetime import datetime, timezone
import dateutil.parser
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.coc_client import CoCClient
from services.db import get_db
from models import ClanMember, ServerConfig, WarHistory

logger = logging.getLogger('bot.scheduler')
coc = CoCClient()

async def sync_all_clans(bot):
    db = get_db()
    try:
        configs = db.query(ServerConfig).all()
        if not configs:
            return
            
        for config in configs:
            clan_tag = config.clan_tag
            
            # CEK LISENSI UNTUK FITUR ALERT (Hanya Standar & Pro)
            tier_status = str(config.tier).lower() if config.tier else "free"
            is_premium = tier_status in ["standar", "pro", "ai_pro"]
            alert_channel = None
            if is_premium and getattr(config, 'alert_channel_id', None):
                alert_channel = bot.get_channel(int(config.alert_channel_id))
            
            # ==========================================
            # 1. MEMBER LEAVE ALERT & SINKRONISASI
            # ==========================================
            clan_data = await coc.get_clan_info(clan_tag)
            
            if clan_data and 'memberList' in clan_data:
                api_tags = [m['tag'] for m in clan_data['memberList']]
                db_members = db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).all()
                
                # Cek member yang ada di DB tapi hilang di Game (Leave)
                for db_m in db_members:
                    if db_m.tag not in api_tags:
                        if alert_channel:
                            await alert_channel.send(f"🚨 **Member Leave Alert:** `{db_m.name}` (TH {db_m.townhall_level}) baru saja keluar dari clan.")
                        db.delete(db_m) # Hapus dari database agar tidak alert dua kali
                
                # Update member yang masih ada
                for member in clan_data['memberList']:
                    db_member = db.query(ClanMember).filter(
                        ClanMember.tag == member['tag'],
                        ClanMember.clan_tag == clan_tag
                    ).first()
                    
                    if not db_member:
                        db_member = ClanMember(tag=member['tag'], clan_tag=clan_tag)
                        db.add(db_member)
                    
                    db_member.name = member['name']
                    db_member.role = member['role']
                    db_member.townhall_level = member['townHallLevel']
                    db_member.donations = member['donations']
                    db_member.donations_received = member['donationsReceived']
                    db_member.last_updated = datetime.utcnow()
            
            # ==========================================
            # 2. AUTO WAR ALERT
            # ==========================================
            war_data = await coc.get_current_war(clan_tag)
            if war_data and war_data.get('state') == 'inWar' and alert_channel:
                try:
                    end_time_str = war_data.get('endTime')
                    # Parse waktu format CoC (CoC API menggunakan format khusus T...Z)
                    end_time = dateutil.parser.isoparse(end_time_str.replace("T", "T").replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    time_diff = end_time - now
                    
                    # Alert jika sisa waktu war antara 1 hingga 2 jam
                    if 3600 <= time_diff.total_seconds() <= 7200:
                        clan_info = war_data.get('clan', {})
                        members = clan_info.get('members', [])
                        
                        no_attackers = []
                        for m in members:
                            attacks = m.get('attacks', [])
                            max_attacks = war_data.get('attacksPerMember', 2)
                            if len(attacks) < max_attacks:
                                no_attackers.append(f"{m.get('name')} ({max_attacks - len(attacks)} Attack Sisa)")
                        
                        if no_attackers:
                            alert_msg = "⚔️ **AUTO WAR ALERT** ⚔️\nWar akan berakhir dalam waktu kurang dari 2 Jam!\n\n**Member belum attack:**\n"
                            alert_msg += "\n".join([f"• {name}" for name in no_attackers])
                            await alert_channel.send(alert_msg)
                except Exception as e:
                    logger.error(f"Gagal parse waktu war untuk alert: {e}")

            # ==========================================
            # 3. WAR HISTORY
            # ==========================================
            war_log = await coc.get_war_log(clan_tag)
            if isinstance(war_log, list) and len(war_log) > 0:
                for war in war_log[:5]: 
                    opponent = war.get('opponent', {})
                    clan = war.get('clan', {})
                    if opponent.get('tag'):
                        existing_war = db.query(WarHistory).filter(
                            WarHistory.clan_tag == clan_tag,
                            WarHistory.opponent_tag == opponent.get('tag')
                        ).first()
                        
                        if not existing_war:
                            new_history = WarHistory(
                                clan_tag=clan_tag,
                                opponent_name=opponent.get('name', 'Unknown'),
                                opponent_tag=opponent.get('tag', ''),
                                result=war.get('result', 'N/A'),
                                stars=clan.get('stars', 0),
                                destruction_percentage=int(clan.get('destructionPercentage', 0))
                            )
                            db.add(new_history)

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error sinkronisasi database: {e}")
    finally:
        db.close()

def start_scheduler(bot):
    scheduler = AsyncIOScheduler()
    # Interval tetap 1 jam agar war alert tidak terlewat
    scheduler.add_job(sync_all_clans, 'interval', hours=1, args=[bot], id='sync_all_clans_job')
    scheduler.start()
    logger.info("Scheduler aktif (Interval: 1 Jam).")
    asyncio.create_task(sync_all_clans(bot))
