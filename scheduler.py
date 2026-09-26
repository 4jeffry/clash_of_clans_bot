import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.coc_client import CoCClient
from services.db import get_db
from models import ClanMember, ServerConfig

logger = logging.getLogger('bot.scheduler')
coc = CoCClient()

async def sync_all_clans():
    db = get_db()
    try:
        # Ambil semua konfigurasi server dari database
        configs = db.query(ServerConfig).all()
        if not configs:
            logger.info("Belum ada server yang melakukan !setup. Skip sinkronisasi.")
            return
            
        logger.info(f"Memulai sinkronisasi untuk {len(configs)} clan...")
        
        for config in configs:
            clan_tag = config.clan_tag
            clan_data = await coc.get_clan_info(clan_tag)
            
            if not clan_data or 'memberList' not in clan_data:
                logger.error(f"Gagal mengambil data member untuk clan {clan_tag}.")
                continue
                
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
        
        db.commit()
        logger.info("Sinkronisasi semua database clan berhasil.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error sinkronisasi database: {e}")
    finally:
        db.close()

def start_scheduler():
    scheduler = AsyncIOScheduler()
    # Otomatis update data setiap 6 jam
    scheduler.add_job(sync_all_clans, 'interval', hours=6, id='sync_all_clans_job')
    scheduler.start()
    logger.info("Scheduler aktif.")
    
    # Panggil langsung pas bot nyala biar tabel gak kosong pas pertama kali setup
    asyncio.create_task(sync_all_clans())
