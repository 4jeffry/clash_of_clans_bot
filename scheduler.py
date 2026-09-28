import logging
import asyncio
from datetime import datetime, timezone
import dateutil.parser
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.coc_client import CoCClient
from services.db import get_db
from models import ClanMember, ServerConfig, WarHistory, War, WarAttack, CWLSeason

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
            
            # CEK LISENSI UNTUK FITUR ALERT (Hanya Member+ / VIP)
            tier_status = str(config.tier).lower() if config.tier else "free"
            is_premium = tier_status in ["standar", "pro", "ai_pro"]
            alert_channel = None
            if is_premium and getattr(config, 'alert_channel_id', None):
                alert_channel = bot.get_channel(int(config.alert_channel_id))
            
            # ==========================================
            # 1. MEMBER LEAVE & JOIN ALERT SINKRONISASI
            # ==========================================
            clan_data = await coc.get_clan_info(clan_tag)
            
            if clan_data and 'memberList' in clan_data:
                api_members = clan_data['memberList']
                api_tags = [m['tag'] for m in api_members]
                db_members = db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).all()
                db_tags = [m.tag for m in db_members]
                
                # Cek Member Keluar
                for db_m in db_members:
                    if db_m.tag not in api_tags:
                        if alert_channel:
                            await alert_channel.send(f"🚨 **Member Keluar:** `{db_m.name}` (TH {db_m.townhall_level}) baru saja meninggalkan clan.")
                        db.delete(db_m)
                
                # Cek Member Masuk & Sinkronisasi Data
                for member in api_members:
                    db_member = db.query(ClanMember).filter(
                        ClanMember.tag == member['tag'],
                        ClanMember.clan_tag == clan_tag
                    ).first()
                    
                    if not db_member:
                        # Syarat len(db_tags) > 0 memastikan alert tidak spam saat pertama kali bot disetup
                        if alert_channel and len(db_tags) > 0:
                            await alert_channel.send(f"👋 **Member Baru Masuk:** Selamat datang `{member['name']}` (TH {member['townHallLevel']}) di clan!")
                            
                        db_member = ClanMember(tag=member['tag'], clan_tag=clan_tag)
                        db.add(db_member)
                    
                    db_member.name = member['name']
                    db_member.role = member['role']
                    db_member.townhall_level = member['townHallLevel']
                    db_member.donations = member['donations']
                    db_member.donations_received = member['donationsReceived']
                    db_member.last_updated = datetime.utcnow()
            
            # ==========================================
            # 2. AUTO WAR ALERT & SINKRONISASI RACE DATA
            # ==========================================
            war_data = await coc.get_current_war(clan_tag)
            if war_data:
                # [A] LOGIKA AUTO WAR ALERT UNTUK SISA WAKTU
                if war_data.get('state') == 'inWar' and alert_channel:
                    try:
                        end_time_str = war_data.get('endTime')
                        end_time = dateutil.parser.isoparse(end_time_str.replace("T", "T").replace("Z", "+00:00"))
                        now = datetime.now(timezone.utc)
                        time_diff = end_time - now
                        
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
                                alert_msg = "⚔️ **AUTO WAR ALERT** ⚔️\nWar akan berakhir dalam waktu kurang dari 2 Jam!\n\n**Member belum attack penuh:**\n"
                                alert_msg += "\n".join([f"• {name}" for name in no_attackers])
                                await alert_channel.send(alert_msg)
                    except Exception as e:
                        logger.error(f"Gagal parse waktu war untuk alert: {e}")

                # [B] LOGIKA NOTIFIKASI STATUS WAR (Prep, Battle, Ended) & SINKRONISASI
                opponent = war_data.get('opponent', {})
                clan_info = war_data.get('clan', {})
                
                if opponent.get('tag'):
                    cwl_group = await coc.get_cwl_group(clan_tag)
                    is_cwl = False
                    cwl_season_id = None
                    
                    if cwl_group and cwl_group.get('state') != 'notInWar':
                        is_cwl = True
                        current_month = datetime.now().strftime('%Y-%m')
                        
                        season = db.query(CWLSeason).filter(
                            CWLSeason.clan_tag == clan_tag, 
                            CWLSeason.month == current_month
                        ).first()
                        
                        if not season:
                            season = CWLSeason(month=current_month, clan_tag=clan_tag)
                            db.add(season)
                            db.commit()
                        cwl_season_id = season.id
                    
                    db_war = db.query(War).filter(
                        War.clan_tag == clan_tag,
                        War.opponent_tag == opponent.get('tag')
                    ).order_by(War.id.desc()).first()
                    
                    if not db_war or (db_war.state == 'warEnded' and war_data.get('state') != 'warEnded'):
                        # PERTANDINGAN BARU TERDETEKSI
                        db_war = War(
                            clan_tag=clan_tag,
                            opponent_tag=opponent.get('tag'),
                            opponent_name=opponent.get('name'),
                            team_size=war_data.get('teamSize', 0),
                            state=war_data.get('state'),
                            is_cwl=is_cwl,
                            cwl_season_id=cwl_season_id
                        )
                        db.add(db_war)
                        db.commit()

                        # NOTIFIKASI 1: PREPARATION DAY DIMULAI
                        if war_data.get('state') == 'preparation' and alert_channel:
                            await alert_channel.send(f"🔍 **War Matchmaking Sukses!**\nKita akan melawan clan **{opponent.get('name')}**. Fase persiapan telah dimulai. Jangan lupa isi CC!")
                    else:
                        if db_war.state != war_data.get('state'):
                            new_state = war_data.get('state')
                            db_war.state = new_state
                            
                            # NOTIFIKASI 2: BATTLE DAY DIMULAI
                            if new_state == 'inWar' and alert_channel:
                                await alert_channel.send(f"⚔️ **Battle Day Dimulai!**\nWar melawan **{opponent.get('name')}** sudah dimulai. Gasken ratakan base musuh!")
                            
                            # NOTIFIKASI 3: WAR BERAKHIR
                            elif new_state == 'warEnded' and alert_channel:
                                await alert_channel.send(f"🛡️ **War Berakhir!**\nWar melawan **{opponent.get('name')}** telah selesai. Ketik `/warstatus` untuk melihat ringkasan akhir.")
                                
                            db.commit()
                    
                    # Sinkronisasi Detail Serangan (Tabel `war_attacks`)
                    if clan_info.get('members'):
                        for m in clan_info['members']:
                            if 'attacks' in m:
                                for idx, atk in enumerate(m['attacks']):
                                    db_atk = db.query(WarAttack).filter(
                                        WarAttack.war_id == db_war.id,
                                        WarAttack.attacker_tag == m.get('tag'),
                                        WarAttack.order_num == (idx + 1)
                                    ).first()
                                    
                                    if not db_atk:
                                        new_atk = WarAttack(
                                            war_id=db_war.id,
                                            attacker_tag=m.get('tag'),
                                            attacker_name=m.get('name'),
                                            defender_tag=atk.get('defenderTag'),
                                            stars=atk.get('stars', 0),
                                            destruction_percentage=atk.get('destructionPercentage', 0),
                                            order_num=(idx + 1)
                                        )
                                        db.add(new_atk)
                        db.commit()

            # ==========================================
            # 3. WAR HISTORY (Tarik 5 War Terakhir)
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
    scheduler.add_job(sync_all_clans, 'interval', hours=1, args=[bot], id='sync_all_clans_job')
    scheduler.start()
    logger.info("Scheduler aktif (Interval: 1 Jam).")
    asyncio.create_task(sync_all_clans(bot))
