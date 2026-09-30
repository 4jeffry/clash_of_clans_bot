import logging
import asyncio
from datetime import datetime, timezone, date
import dateutil.parser
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text

from services.coc_client import CoCClient
from services.db import get_db
from models import ClanMember, ServerConfig, WarHistory, War, WarAttack, CWLSeason, WarParticipant, MemberSnapshot

logger = logging.getLogger('bot.scheduler')
coc = CoCClient()

def _parse_time(time_str: str):
    if not time_str: return None
    try:
        return dateutil.parser.isoparse(time_str.replace("T", "T").replace("Z", "+00:00"))
    except:
        return None

async def sync_all_clans(bot):
    db = get_db()
    try:
        configs = db.query(ServerConfig).all()
        if not configs:
            return
            
        for config in configs:
            clan_tag = config.clan_tag
            
            # CEK LISENSI
            tier_status = str(config.tier).lower() if config.tier else "free"
            is_premium = tier_status in ["standar", "pro", "ai_pro"]
            alert_channel = None
            if is_premium and getattr(config, 'alert_channel_id', None):
                alert_channel = bot.get_channel(int(config.alert_channel_id))
            
            # ==========================================
            # 1. MEMBER LEAVE & JOIN ALERT + SNAPSHOT
            # ==========================================
            clan_data = await coc.get_clan_info(clan_tag)
            
            if clan_data and 'memberList' in clan_data:
                api_members = clan_data['memberList']
                api_tags = [m['tag'] for m in api_members]
                db_members = db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).all()
                db_tags = [m.tag for m in db_members]
                
                # Cek Keluar
                for db_m in db_members:
                    if db_m.tag not in api_tags:
                        if alert_channel:
                            await alert_channel.send(f"🚨 **Member Keluar:** `{db_m.name}` (TH {db_m.townhall_level}) baru saja meninggalkan clan.")
                        db.delete(db_m)
                
                today = date.today()
                
                # Sinkronisasi Member & Daily Snapshot
                for member in api_members:
                    # Update tabel utama (ClanMember)
                    db_member = db.query(ClanMember).filter(
                        ClanMember.tag == member['tag'],
                        ClanMember.clan_tag == clan_tag
                    ).first()
                    
                    if not db_member:
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
                    
                    # 🚀 UPSERT MemberSnapshot (Harian - untuk Data AI/Pro)
                    try:
                        heroes_data = member.get('heroes', [])
                        equipment_data = member.get('heroEquipment', [])
                        
                        stmt = insert(MemberSnapshot).values(
                            player_tag=member['tag'],
                            clan_tag=clan_tag,
                            snap_date=today,
                            townhall_level=member['townHallLevel'],
                            trophies=member.get('trophies', 0),
                            war_stars=member.get('warStars', 0),
                            war_preference=member.get('warPreference', 'unknown'),
                            donations=member.get('donations', 0),
                            donations_received=member.get('donationsReceived', 0),
                            heroes=heroes_data,
                            equipment=equipment_data
                        )
                        stmt = stmt.on_conflict_do_update(
                            index_elements=['player_tag', 'snap_date'],
                            set_=dict(
                                townhall_level=stmt.excluded.townhall_level,
                                trophies=stmt.excluded.trophies,
                                war_stars=stmt.excluded.war_stars,
                                war_preference=stmt.excluded.war_preference,
                                donations=stmt.excluded.donations,
                                donations_received=stmt.excluded.donations_received,
                                heroes=stmt.excluded.heroes,
                                equipment=stmt.excluded.equipment
                            )
                        )
                        db.execute(stmt)
                    except Exception as e:
                        logger.error(f"Gagal upsert snapshot member {member['tag']}: {e}")
                
                db.commit()
            
            # ==========================================
            # 2. AUTO WAR ALERT & SINKRONISASI LENGKAP
            # ==========================================
            war_data = await coc.get_current_war(clan_tag)
            if war_data:
                state = war_data.get('state')
                opponent = war_data.get('opponent', {})
                clan_info = war_data.get('clan', {})
                
                # Auto Alert Waktu War (Hanya saat inWar)
                if state == 'inWar' and alert_channel:
                    try:
                        end_time = _parse_time(war_data.get('endTime'))
                        now = datetime.now(timezone.utc)
                        if end_time:
                            time_diff = end_time - now
                            if 3600 <= time_diff.total_seconds() <= 7200:
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
                    
                    start_t = _parse_time(war_data.get('startTime'))
                    end_t = _parse_time(war_data.get('endTime'))
                    
                    if not db_war or (db_war.state == 'warEnded' and state != 'warEnded'):
                        # PERTANDINGAN BARU TERDETEKSI
                        db_war = War(
                            clan_tag=clan_tag,
                            opponent_tag=opponent.get('tag'),
                            opponent_name=opponent.get('name'),
                            team_size=war_data.get('teamSize', 0),
                            state=state,
                            is_cwl=is_cwl,
                            cwl_season_id=cwl_season_id,
                            start_time=start_t,
                            end_time=end_t,
                            attacks_per_member=war_data.get('attacksPerMember', 2)
                        )
                        db.add(db_war)
                        db.commit()

                        if state == 'preparation' and alert_channel:
                            await alert_channel.send(f"🔍 **War Matchmaking Sukses!**\nKita akan melawan clan **{opponent.get('name')}**.")
                    else:
                        # UPDATE STATUS WAR BERJALAN
                        new_state = state
                        if db_war.state != new_state:
                            db_war.state = new_state
                            if new_state == 'inWar' and alert_channel:
                                await alert_channel.send(f"⚔️ **Battle Day Dimulai!**\nWar melawan **{opponent.get('name')}** sudah dimulai.")
                            elif new_state == 'warEnded' and alert_channel:
                                await alert_channel.send(f"🛡️ **War Berakhir!**\nWar melawan **{opponent.get('name')}** telah selesai.")
                        
                        # Update skor berjalan
                        db_war.clan_stars = clan_info.get('stars', 0)
                        db_war.clan_destruction = clan_info.get('destructionPercentage', 0.0)
                        db_war.opp_stars = opponent.get('stars', 0)
                        db_war.opp_destruction = opponent.get('destructionPercentage', 0.0)
                        db.commit()
                    
                    # 🚀 UPSERT WAR PARTICIPANTS
                    try:
                        all_members = clan_info.get('members', [])
                        for m in all_members:
                            stmt = insert(WarParticipant).values(
                                war_id=db_war.id,
                                player_tag=m.get('tag'),
                                player_name=m.get('name'),
                                townhall_level=m.get('townhallLevel', 0),
                                map_position=m.get('mapPosition', 0),
                                attacks_used=len(m.get('attacks', [])),
                                attacks_allowed=war_data.get('attacksPerMember', 2)
                            )
                            stmt = stmt.on_conflict_do_update(
                                index_elements=['war_id', 'player_tag'],
                                set_=dict(
                                    map_position=stmt.excluded.map_position,
                                    attacks_used=stmt.excluded.attacks_used,
                                    townhall_level=stmt.excluded.townhall_level
                                )
                            )
                            db.execute(stmt)
                        db.commit()
                    except Exception as e:
                        logger.error(f"Gagal upsert war_participants: {e}")
                    
                    # 🚀 UPSERT WAR ATTACKS (CLAN KITA & MUSUH) + NET STARS
                    def process_attacks(attacker_members, is_our_clan):
                        for m in attacker_members:
                            attacks = m.get('attacks', [])
                            for atk in attacks:
                                
                                # Default value
                                atk_th = m.get('townhallLevel', 0)
                                def_th = 0
                                atk_pos = m.get('mapPosition', 0)
                                def_pos = 0
                                is_fresh = True
                                net_stars = atk.get('stars', 0)
                                
                                # Tarik data defender untuk dihitung TH & Posisinya
                                defender_tag = atk.get('defenderTag')
                                target_members = opponent.get('members', []) if is_our_clan else clan_info.get('members', [])
                                
                                defender = next((t for t in target_members if t.get('tag') == defender_tag), None)
                                if defender:
                                    def_th = defender.get('townhallLevel', 0)
                                    def_pos = defender.get('mapPosition', 0)
                                    
                                    # Hitung Net Stars & Fresh Hit
                                    # Logic sederhana: Jika attacker order != 1, cek best defense sblmnya. (Di API CoC, defender punya 'bestOpponentAttack')
                                    # Jika bestOpponentAttack ada, kita asumsikan hit ini bukan fresh jika order > 1, tapi butuh agregasi. 
                                    # Untuk aman, is_fresh diset berdasarkan total def dari target tersebut.
                                    
                                stmt = insert(WarAttack).values(
                                    war_id=db_war.id,
                                    attacker_tag=m.get('tag'),
                                    attacker_name=m.get('name'),
                                    defender_tag=defender_tag,
                                    stars=atk.get('stars', 0),
                                    destruction_percentage=atk.get('destructionPercentage', 0),
                                    order_num=atk.get('order', 1),
                                    attacker_th=atk_th,
                                    defender_th=def_th,
                                    attacker_map_position=atk_pos,
                                    defender_map_position=def_pos,
                                    is_fresh_attack=is_fresh,
                                    net_stars=net_stars
                                )
                                stmt = stmt.on_conflict_do_update(
                                    index_elements=['war_id', 'attacker_tag', 'order_num'],
                                    set_=dict(
                                        stars=stmt.excluded.stars,
                                        destruction_percentage=stmt.excluded.destruction_percentage,
                                        attacker_th=stmt.excluded.attacker_th,
                                        defender_th=stmt.excluded.defender_th,
                                        attacker_map_position=stmt.excluded.attacker_map_position,
                                        defender_map_position=stmt.excluded.defender_map_position
                                    )
                                )
                                db.execute(stmt)

                    try:
                        # Masukkan Serangan Klan Kita (Offense)
                        process_attacks(clan_info.get('members', []), True)
                        # Masukkan Serangan Musuh (Defense - Biar nilai defense gak kosong lagi!)
                        process_attacks(opponent.get('members', []), False)
                        db.commit()
                    except Exception as e:
                        logger.error(f"Gagal upsert war_attacks: {e}")

            # ==========================================
            # 3. WAR HISTORY (Tarik 5 War Terakhir)
            # ==========================================
            war_log = await coc.get_war_log(clan_tag)
            if isinstance(war_log, list) and len(war_log) > 0:
                for w in war_log[:5]: 
                    opp = w.get('opponent', {})
                    cl = w.get('clan', {})
                    if opp.get('tag'):
                        existing_war = db.query(WarHistory).filter(
                            WarHistory.clan_tag == clan_tag,
                            WarHistory.opponent_tag == opp.get('tag')
                        ).first()
                        
                        if not existing_war:
                            new_history = WarHistory(
                                clan_tag=clan_tag,
                                opponent_name=opp.get('name', 'Unknown'),
                                opponent_tag=opp.get('tag', ''),
                                result=w.get('result', 'N/A'),
                                stars=cl.get('stars', 0),
                                destruction_percentage=int(cl.get('destructionPercentage', 0.0))
                            )
                            db.add(new_history)

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error sinkronisasi database (Main Scheduler Loop): {e}")
    finally:
        db.close()

def start_scheduler(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(sync_all_clans, 'interval', hours=1, args=[bot], id='sync_all_clans_job')
    scheduler.start()
    logger.info("Scheduler aktif (Interval: 1 Jam).")
    asyncio.create_task(sync_all_clans(bot))
