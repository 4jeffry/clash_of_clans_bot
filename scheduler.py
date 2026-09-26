import logging
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.coc_client import CoCClient
from services.db import get_db
from models import ClanMember, ServerConfig, WarHistory

logger = logging.getLogger('bot.scheduler')
coc = CoCClient()

async def sync_all_clans():
    db = get_db()
    try:
        # Ambil semua konfigurasi server dari database
        configs = db.query(ServerConfig).all()
        if not configs:
            logger.info("Belum ada server yang melakukan /setup. Skip sinkronisasi.")
            return
            
        logger.info(f"Memulai sinkronisasi untuk {len(configs)} clan...")
        
        for config in configs:
            clan_tag = config.clan_tag
            
            # ==========================================
            # 1. SINKRONISASI DATA MEMBER & DONASI
            # ==========================================
            clan_data = await coc.get_clan_info(clan_tag)
            
            if clan_data and 'memberList' in clan_data:
                for member in clan_data['memberList']:
                    # Cocokkan tag player dan clan_tag agar tidak kecampur
                    db_member = db.query(ClanMember).filter(
                        ClanMember.tag == member['tag'],
                        ClanMember.clan_tag == clan_tag
                    ).first()
                    
                    if not db_member:
                        # Masukkan clan_tag saat membuat member baru
                        db_member = ClanMember(tag=member['tag'], clan_tag=clan_tag)
                        db.add(db_member)
                    
                    db_member.name = member['name']
                    db_member.role = member['role']
                    db_member.townhall_level = member['townHallLevel']
                    db_member.donations = member['donations']
                    db_member.donations_received = member['donationsReceived']
                    db_member.last_updated = datetime.utcnow()
            else:
                logger.error(f"Gagal mengambil data member untuk clan {clan_tag}.")
            
            # ==========================================
            # 2. SINKRONISASI DATA WAR HISTORY
            # ==========================================
            war_log = await coc.get_war_log(clan_tag)
            if isinstance(war_log, list) and len(war_log) > 0:
                # Ambil 5 war terakhir saja biar prosesnya ringan
                for war in war_log[:5]: 
                    opponent = war.get('opponent', {})
                    clan = war.get('clan', {})
                    
                    # Pastikan tag lawan ada, lalu cek apakah war ini udah tersimpan di database
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
        logger.info("Sinkronisasi semua database clan (Member & War History) berhasil.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error sinkronisasi database: {e}")
    finally:
        db.close()

def start_scheduler():
    scheduler = AsyncIOScheduler()
    # Interval diubah jadi 1 jam agar data AI lebih real-time dan akurat
    scheduler.add_job(sync_all_clans, 'interval', hours=1, id='sync_all_clans_job')
    scheduler.start()
    logger.info("Scheduler aktif (Interval: 1 Jam).")
    
    # Panggil langsung pas bot nyala biar tabel gak kosong pas pertama kali setup
    asyncio.create_task(sync_all_clans())
