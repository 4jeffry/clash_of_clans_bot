import os
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.coc_client import CoCClient
from services.db import get_db
from models import ClanMember

logger = logging.getLogger('bot.scheduler')
coc = CoCClient()
clan_tag = os.getenv('CLAN_TAG')

async def sync_clan_members():
    if not clan_tag:
        logger.error("CLAN_TAG kosong. Skip sinkronisasi.")
        return
        
    logger.info("Memulai sinkronisasi data member ke database...")
    clan_data = await coc.get_clan_info(clan_tag)
    
    if not clan_data or 'memberList' not in clan_data:
        logger.error("Gagal mendapatkan data member untuk sinkronisasi.")
        return
        
    db = get_db()
    try:
        for member in clan_data['memberList']:
            db_member = db.query(ClanMember).filter(ClanMember.tag == member['tag']).first()
            
            if not db_member:
                db_member = ClanMember(tag=member['tag'])
                db.add(db_member)
            
            db_member.name = member['name']
            db_member.role = member['role']
            db_member.townhall_level = member['townHallLevel']
            db_member.donations = member['donations']
            db_member.donations_received = member['donationsReceived']
        
        db.commit()
        logger.info("Sinkronisasi database berhasil.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error sinkronisasi database: {e}")
    finally:
        db.close()

def start_scheduler():
    scheduler = AsyncIOScheduler()
    # Otomatis update data setiap 6 jam
    scheduler.add_job(sync_clan_members, 'interval', hours=6)
    scheduler.start()
    logger.info("Scheduler aktif.")
