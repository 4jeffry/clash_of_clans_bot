import logging
import asyncio
from datetime import datetime, timezone, date
import dateutil.parser
from sqlalchemy.dialects.postgresql import insert

from services.coc_client import CoCClient
from services.db import get_db
from models import ClanMember, ServerConfig, WarHistory, War, WarAttack, CWLSeason, WarParticipant, MemberSnapshot

logger = logging.getLogger('bot.sync_worker')

# Set in-memory penanda alert
_alerted_wars = set()

def _parse_time(time_str: str):
    if not time_str: return None
    try:
        return dateutil.parser.isoparse(time_str.replace("T", "T").replace("Z", "+00:00"))
    except:
        return None

def run_heavy_sync_task():
    """Fungsi ini berjalan di thread terpisah. Tidak boleh ada 'await' di sini."""
    alerts_to_send = []
    coc = CoCClient() 
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        db = get_db()
        try:
            # 0. CEK DAN RESET EXPIRED TRIAL/TIER (Best Practice Fix)
            now_utc = datetime.now(timezone.utc)
            expired_configs = db.query(ServerConfig).filter(
                ServerConfig.tier != 'free',
                ServerConfig.expired_at != None,
                ServerConfig.expired_at < now_utc
            ).all()
            
            for cfg in expired_configs:
                logger.info(f"Menurunkan tier {cfg.clan_tag} ke free karena masa aktif habis.")
                cfg.tier = 'free'
                cfg.expired_at = None
                
            if expired_configs:
                db.commit()
                
            # Ambil ulang data config setelah reset
            configs = db.query(ServerConfig).all()
            config_list = [{"clan_tag": c.clan_tag, "tier": c.tier, "alert_channel_id": c.alert_channel_id} for c in configs]
        except Exception as e:
            db.rollback()
            logger.error(f"Error mengambil config atau reset tier: {e}")
            config_list = []
        finally:
            db.close()
        
        if not config_list:
            return alerts_to_send
            
        for config in config_list:
            clan_tag = config['clan_tag']
            alert_ch_id = config['alert_channel_id']
            
            clan_data = loop.run_until_complete(coc.get_clan_info(clan_tag))
            if not clan_data:
                continue
                
            db = get_db()
            try:
                # 1. MEMBER SYNC
                api_members = clan_data.get('memberList', [])
                api_tags = [m['tag'] for m in api_members]
                db_members = db.query(ClanMember).filter(ClanMember.clan_tag == clan_tag).all()
                db_tags = [m.tag for m in db_members]

                for db_m in db_members:
                    if db_m.tag not in api_tags:
                        if alert_ch_id: alerts_to_send.append((alert_ch_id, f"🚨 **Member Keluar:** `{db_m.name}` (TH {db_m.townhall_level}) baru saja meninggalkan clan."))
                        db.delete(db_m)

                for member in api_members:
                    db_member = next((m for m in db_members if m.tag == member['tag']), None)
                    if not db_member:
                        if alert_ch_id and len(db_tags) > 0:
                            alerts_to_send.append((alert_ch_id, f"👋 **Member Baru Masuk:** Selamat datang `{member['name']}` (TH {member['townHallLevel']}) di clan!"))
                        db_member = ClanMember(tag=member['tag'], clan_tag=clan_tag)
                        db.add(db_member)
                    db_member.name = member['name']
                    db_member.role = member['role']
                    db_member.townhall_level = member['townHallLevel']
                    db_member.donations = member['donations']
                    db_member.donations_received = member['donationsReceived']
                    db_member.last_updated = datetime.utcnow()
                db.commit()
                
                # 2. DAILY SNAPSHOT
                today = date.today()
                existing_snaps = db.query(MemberSnapshot.player_tag).filter(
                    MemberSnapshot.clan_tag == clan_tag,
                    MemberSnapshot.snap_date == today
                ).all()
                existing_tags = {snap[0] for snap in existing_snaps}
                missing_tags = [t for t in api_tags if t not in existing_tags][:20]

                if missing_tags:
                    snapshots_batch = []
                    for tag in missing_tags:
                        player_data = loop.run_until_complete(coc.get_player_info(tag))
                        if player_data:
                            heroes_data = [h for h in player_data.get('heroes', []) if h.get('village') == 'home']
                            equipment_data = player_data.get('heroEquipment', [])
                            snapshots_batch.append({
                                'player_tag': tag,
                                'clan_tag': clan_tag,
                                'snap_date': today,
                                'townhall_level': player_data.get('townHallLevel', 0),
                                'trophies': player_data.get('trophies', 0),
                                'war_stars': player_data.get('warStars', 0),
                                'war_preference': player_data.get('warPreference', 'unknown'),
                                'donations': player_data.get('donations', 0),
                                'donations_received': player_data.get('donationsReceived', 0),
                                'heroes': heroes_data,
                                'equipment': equipment_data
                            })
                    
                    if snapshots_batch:
                        stmt = insert(MemberSnapshot).values(snapshots_batch)
                        stmt = stmt.on_conflict_do_nothing(index_elements=['player_tag', 'snap_date'])
                        db.execute(stmt)
                        db.commit()

            except Exception as e:
                db.rollback()
                logger.error(f"Error member/snapshot sync for {clan_tag}: {e}")
            finally:
                db.close()

            # 3. WAR SYNC
            war_data = loop.run_until_complete(coc.get_current_war(clan_tag))
            if war_data and war_data.get('state') != 'notInWar':
                db = get_db()
                try:
                    state = war_data.get('state')
                    opponent = war_data.get('opponent', {})
                    clan_info = war_data.get('clan', {})
                    start_t_str = war_data.get('startTime')
                    
                    war_marker = f"{clan_tag}_{opponent.get('tag')}_{start_t_str}"
                    
                    if state == 'inWar' and alert_ch_id:
                        end_time = _parse_time(war_data.get('endTime'))
                        now = datetime.now(timezone.utc)
                        if end_time:
                            time_diff = end_time - now
                            if 3600 <= time_diff.total_seconds() <= 7200 and war_marker not in _alerted_wars:
                                members = clan_info.get('members', [])
                                max_attacks = war_data.get('attacksPerMember', 2)
                                no_attackers = [
                                    f"{m.get('name')} ({max_attacks - len(m.get('attacks', []))} Attack Sisa)"
                                    for m in members if len(m.get('attacks', [])) < max_attacks
                                ]
                                
                                if no_attackers:
                                    alert_msg = "⚔️ **AUTO WAR ALERT** ⚔️\nWar akan berakhir dalam waktu kurang dari 2 Jam!\n\n**Member belum attack penuh:**\n"
                                    alert_msg += "\n".join([f"• {name}" for name in no_attackers])
                                    alerts_to_send.append((alert_ch_id, alert_msg))
                                    _alerted_wars.add(war_marker)
                                    
                    if state == 'warEnded':
                        _alerted_wars.discard(war_marker)

                    if opponent.get('tag'):
                        cwl_group = loop.run_until_complete(coc.get_cwl_group(clan_tag))
                        is_cwl = cwl_group is not None and cwl_group.get('state') != 'notInWar'
                        
                        cwl_season_id = None
                        if is_cwl:
                            current_month = datetime.now().strftime('%Y-%m')
                            season = db.query(CWLSeason).filter(CWLSeason.clan_tag == clan_tag, CWLSeason.month == current_month).first()
                            if not season:
                                season = CWLSeason(month=current_month, clan_tag=clan_tag)
                                db.add(season)
                                db.commit()
                            cwl_season_id = season.id

                        start_t = _parse_time(start_t_str)
                        end_t = _parse_time(war_data.get('endTime'))
                        
                        db_war = db.query(War).filter(War.clan_tag == clan_tag, War.opponent_tag == opponent.get('tag')).order_by(War.id.desc()).first()
                        
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
                            if state == 'preparation' and alert_ch_id:
                                alerts_to_send.append((alert_ch_id, f"🔍 **War Matchmaking Sukses!**\nKita akan melawan clan **{opponent.get('name')}**."))
                        else:
                            old_state = db_war.state
                            if old_state != state:
                                db_war.state = state
                                if state == 'inWar' and alert_ch_id:
                                    alerts_to_send.append((alert_ch_id, f"⚔️ **Battle Day Dimulai!**\nWar melawan **{opponent.get('name')}** sudah dimulai."))
                                elif state == 'warEnded' and alert_ch_id:
                                    alerts_to_send.append((alert_ch_id, f"🛡️ **War Berakhir!**\nWar melawan **{opponent.get('name')}** telah selesai."))
                            
                            db_war.start_time = start_t
                            db_war.end_time = end_t
                            db_war.clan_stars = clan_info.get('stars', 0)
                            db_war.clan_destruction = clan_info.get('destructionPercentage', 0.0)
                            db_war.opp_stars = opponent.get('stars', 0)
                            db_war.opp_destruction = opponent.get('destructionPercentage', 0.0)
                            db.commit()

                        war_id_local = db_war.id
                        
                        participants_data = []
                        all_members = clan_info.get('members', [])
                        for m in all_members:
                            best_opp = m.get('bestOpponentAttack', {})
                            participants_data.append({
                                'war_id': war_id_local,
                                'player_tag': m.get('tag'),
                                'player_name': m.get('name'),
                                'townhall_level': m.get('townhallLevel', 0),
                                'map_position': m.get('mapPosition', 0),
                                'attacks_used': len(m.get('attacks', [])),
                                'attacks_allowed': war_data.get('attacksPerMember', 2),
                                'opp_attacks_count': m.get('opponentAttacks', 0),
                                'best_opp_stars': best_opp.get('stars', 0),
                                'best_opp_destruction': best_opp.get('destructionPercentage', 0.0)
                            })
                            
                        if participants_data:
                            stmt = insert(WarParticipant).values(participants_data)
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
                        attacks_batch = []
                        
                        for atk in flat_attacks:
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

                            attacks_batch.append({
                                'war_id': war_id_local,
                                'attacker_tag': atk.get('attacker_tag'),
                                'attacker_name': atk.get('attacker_name'),
                                'defender_tag': defender_tag,
                                'stars': stars,
                                'destruction_percentage': atk.get('destructionPercentage', 0),
                                'order_num': atk.get('order', 1),
                                'attacker_th': atk.get('attacker_th'),
                                'defender_th': def_th,
                                'attacker_map_position': atk.get('attacker_pos'),
                                'defender_map_position': def_pos,
                                'is_fresh_attack': is_fresh,
                                'net_stars': net_stars
                            })

                        if attacks_batch:
                            stmt = insert(WarAttack).values(attacks_batch)
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
                except Exception as e:
                    db.rollback()
                    logger.error(f"Error war sync for {clan_tag}: {e}")
                finally:
                    db.close()

            # 4. WAR HISTORY
            war_log = loop.run_until_complete(coc.get_war_log(clan_tag))
            if isinstance(war_log, list) and len(war_log) > 0:
                db = get_db()
                try:
                    for w in war_log[:5]:
                        opp = w.get('opponent', {})
                        cl = w.get('clan', {})
                        if opp.get('tag'):
                            existing_war = db.query(WarHistory).filter(WarHistory.clan_tag == clan_tag, WarHistory.opponent_tag == opp.get('tag')).first()
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
                finally:
                    db.close()
                    
    finally:
        loop.close()
        
    return alerts_to_send
