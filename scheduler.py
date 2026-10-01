import logging
import asyncio
from datetime import datetime, timezone, date
import dateutil.parser
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.dialects.postgresql import insert

from services.coc_client import CoCClient
from services.db import get_db
from models import ClanMember, ServerConfig, WarHistory, War, WarAttack, CWLSeason, WarParticipant, MemberSnapshot

logger = logging.getLogger('bot.scheduler')
coc = CoCClient()

# Set in-memory untuk melacak alert sisa waktu war yang sudah terkirim
_alerted_wars = set()

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
            tier_status = str(config.tier).lower() if config.tier else "free"
            is_premium = tier_status in ["standar", "pro", "ai_pro"]
            alert_channel = None
            if is_premium and getattr(config, 'alert_channel_id', None):
                alert_channel = bot.get_channel(int(config.alert_channel_id))
            
            # ==========================================
            # 1. CLAN MEMBER & SNAPSHOT SYNC
            # ==========================================
            try:
                clan_data = await coc.get_clan_info(clan_tag)
                if clan_data and 'memberList' in clan_data:
                    api_members = clan_data['memberList']
                    api_tags = [m['tag'] for m in api_members]
                    db_members = db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).all()
                    db_tags = [m.tag for m in db_members]
                    
                    for db_m in db_members:
                        if db_m.tag not in api_tags:
                            if alert_channel:
                                await alert_channel.send(f"🚨 **Member Keluar:** `{db_m.name}` (TH {db_m.townhall_level}) baru saja meninggalkan clan.")
                            db.delete(db_m)
                    
                    for member in api_members:
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
                    db.commit()

                    # Daily Snapshot (Isolasi Per Player)
                    today = date.today()
                    existing_snaps = db.query(MemberSnapshot.player_tag).filter(
                        MemberSnapshot.clan_tag == clan_tag,
                        MemberSnapshot.snap_date == today
                    ).all()
                    existing_tags = {snap[0] for snap in existing_snaps}

                    for mem in api_members:
                        tag = mem['tag']
                        if tag not in existing_tags:
                            try:
                                player_data = await coc.get_player_info(tag)
                                if player_data:
                                    heroes_data = [h for h in player_data.get('heroes', []) if h.get('village') == 'home']
                                    equipment_data = player_data.get('heroEquipment', [])
                                    
                                    stmt = insert(MemberSnapshot).values(
                                        player_tag=tag,
                                        clan_tag=clan_tag,
                                        snap_date=today,
                                        townhall_level=player_data.get('townHallLevel', 0),
                                        trophies=player_data.get('trophies', 0),
                                        war_stars=player_data.get('warStars', 0),
                                        war_preference=player_data.get('warPreference', 'unknown'),
                                        donations=player_data.get('donations', 0),
                                        donations_received=player_data.get('donationsReceived', 0),
                                        heroes=heroes_data,
                                        equipment=equipment_data
                                    )
                                    stmt = stmt.on_conflict_do_nothing(index_elements=['player_tag', 'snap_date'])
                                    db.execute(stmt)
                                    db.commit()
                            except Exception as inner_e:
                                db.rollback()
                                logger.error(f"Failed to upsert snapshot for {tag}: {inner_e}")
                            
                            await asyncio.sleep(0.1)
            except Exception as e:
                db.rollback()
                logger.error(f"Error syncing members/snapshots for {clan_tag}: {e}")

            # ==========================================
            # 2. WAR SYNC & ALERT
            # ==========================================
            try:
                war_data = await coc.get_current_war(clan_tag)
                if war_data and war_data.get('state') != 'notInWar':
                    state = war_data.get('state')
                    opponent = war_data.get('opponent', {})
                    clan_info = war_data.get('clan', {})
                    start_t = _parse_time(war_data.get('startTime'))
                    end_t = _parse_time(war_data.get('endTime'))
                    
                    war_marker = f"{clan_tag}_{opponent.get('tag')}_{war_data.get('startTime')}"
                    
                    # Auto Alert Sisa Waktu
                    if state == 'inWar' and alert_channel:
                        now = datetime.now(timezone.utc)
                        if end_t:
                            time_diff = end_t - now
                            if 3600 <= time_diff.total_seconds() <= 7200 and war_marker not in _alerted_wars:
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
                                    _alerted_wars.add(war_marker)

                    if opponent.get('tag'):
                        cwl_group = await coc.get_cwl_group(clan_tag)
                        is_cwl = cwl_group is not None and cwl_group.get('state') != 'notInWar'
                        cwl_season_id = None
                        
                        if is_cwl:
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
                        
                        if not db_war or (db_war.state == 'warEnded' and state != 'warEnded'):
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
                            old_state = db_war.state
                            if old_state != state:
                                db_war.state = state
                                if state == 'inWar' and alert_channel:
                                    await alert_channel.send(f"⚔️ **Battle Day Dimulai!**\nWar melawan **{opponent.get('name')}** sudah dimulai.")
                                elif state == 'warEnded':
                                    if alert_channel:
                                        await alert_channel.send(f"🛡️ **War Berakhir!**\nWar melawan **{opponent.get('name')}** telah selesai.")
                                    _alerted_wars.discard(war_marker)
                            
                            db_war.start_time = start_t
                            db_war.end_time = end_t
                            db_war.clan_stars = clan_info.get('stars', 0)
                            db_war.clan_destruction = clan_info.get('destructionPercentage', 0.0)
                            db_war.opp_stars = opponent.get('stars', 0)
                            db_war.opp_destruction = opponent.get('destructionPercentage', 0.0)
                            
                            if state == 'warEnded':
                                clan_s, opp_s = db_war.clan_stars, db_war.opp_stars
                                clan_d, opp_d = db_war.clan_destruction, db_war.opp_destruction
                                if clan_s > opp_s:
                                    db_war.result = 'win'
                                elif clan_s < opp_s:
                                    db_war.result = 'lose'
                                else:
                                    if clan_d > opp_d: db_war.result = 'win'
                                    elif clan_d < opp_d: db_war.result = 'lose'
                                    else: db_war.result = 'tie'
                                
                            db.commit()
                        
                        # Upsert War Participants & Ringkasan Pertahanan Musuh (Isolasi Per Player)
                        all_members = clan_info.get('members', [])
                        for m in all_members:
                            try:
                                best_opp = m.get('bestOpponentAttack', {})
                                stmt = insert(WarParticipant).values(
                                    war_id=db_war.id,
                                    player_tag=m.get('tag'),
                                    player_name=m.get('name'),
                                    townhall_level=m.get('townhallLevel', 0),
                                    map_position=m.get('mapPosition', 0),
                                    attacks_used=len(m.get('attacks', [])),
                                    attacks_allowed=war_data.get('attacksPerMember', 2),
                                    opp_attacks_count=m.get('opponentAttacks', 0),
                                    best_opp_stars=best_opp.get('stars', 0),
                                    best_opp_destruction=best_opp.get('destructionPercentage', 0.0)
                                )
                                stmt = stmt.on_conflict_do_update(
                                    index_elements=['war_id', 'player_tag'],
                                    set_=dict(
                                        map_position=stmt.excluded.map_position,
                                        attacks_used=stmt.excluded.attacks_used,
                                        townhall_level=stmt.excluded.townhall_level,
                                        opp_attacks_count=stmt.excluded.opp_attacks_count,
                                        best_opp_stars=stmt.excluded.best_opp_stars,
                                        best_opp_destruction=stmt.excluded.best_opp_destruction
                                    )
                                )
                                db.execute(stmt)
                                db.commit()
                            except Exception as inner_e:
                                db.rollback()
                                logger.error(f"Error participant {m.get('tag')}: {inner_e}")
                        
                        # Upsert War Attacks & Net Stars Logic (Isolasi Per Attack)
                        flat_attacks = []
                        for m in all_members:
                            for atk in m.get('attacks', []):
                                atk_data = dict(atk)
                                atk_data['attacker_tag'] = m.get('tag')
                                atk_data['attacker_name'] = m.get('name')
                                atk_data['attacker_th'] = m.get('townhallLevel', 0)
                                atk_data['attacker_pos'] = m.get('mapPosition', 0)
                                flat_attacks.append(atk_data)
                                
                        flat_attacks.sort(key=lambda x: x.get('order', 0))
                        
                        attacked_bases = set()
                        best_stars_on_base = {}
                        
                        for atk in flat_attacks:
                            try:
                                defender_tag = atk.get('defenderTag')
                                stars = atk.get('stars', 0)
                                
                                is_fresh = defender_tag not in attacked_bases
                                attacked_bases.add(defender_tag)
                                
                                prev_best = best_stars_on_base.get(defender_tag, 0)
                                net_stars = max(0, stars - prev_best)
                                
                                if stars > prev_best:
                                    best_stars_on_base[defender_tag] = stars
                                    
                                opp_members = opponent.get('members', [])
                                defender = next((t for t in opp_members if t.get('tag') == defender_tag), None)
                                def_th = defender.get('townhallLevel', 0) if defender else 0
                                def_pos = defender.get('mapPosition', 0) if defender else 0

                                stmt = insert(WarAttack).values(
                                    war_id=db_war.id,
                                    attacker_tag=atk.get('attacker_tag'),
                                    attacker_name=atk.get('attacker_name'),
                                    defender_tag=defender_tag,
                                    stars=stars,
                                    destruction_percentage=atk.get('destructionPercentage', 0),
                                    order_num=atk.get('order', 1),
                                    attacker_th=atk.get('attacker_th'),
                                    defender_th=def_th,
                                    attacker_map_position=atk.get('attacker_pos'),
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
                                        defender_map_position=stmt.excluded.defender_map_position,
                                        is_fresh_attack=stmt.excluded.is_fresh_attack,
                                        net_stars=stmt.excluded.net_stars
                                    )
                                )
                                db.execute(stmt)
                                db.commit()
                            except Exception as inner_e:
                                db.rollback()
                                logger.error(f"Error attack {atk.get('attacker_tag')}: {inner_e}")
            except Exception as e:
                db.rollback()
                logger.error(f"Error syncing war data for {clan_tag}: {e}")

            # ==========================================
            # 3. WAR HISTORY (Untuk AI Opponent)
            # ==========================================
            try:
                war_log = await coc.get_war_log(clan_tag)
                if isinstance(war_log, list) and len(war_log) > 0:
                    for w in war_log[:5]: 
                        try:
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
                        except Exception as inner_e:
                            db.rollback()
                            logger.error(f"Error processing war log entry: {inner_e}")
            except Exception as e:
                db.rollback()
                logger.error(f"Error syncing war history for {clan_tag}: {e}")

    except Exception as e:
        logger.error(f"Critical error in main scheduler loop: {e}")
    finally:
        db.close()

def start_scheduler(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(sync_all_clans, 'interval', minutes=10, args=[bot], id='sync_all_clans_job')
    scheduler.start()
    logger.info("Scheduler aktif (Interval: 10 Menit).")
    asyncio.create_task(sync_all_clans(bot))
