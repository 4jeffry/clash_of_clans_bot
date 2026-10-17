import logging
import asyncio
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.sync_worker import run_heavy_sync_task

logger = logging.getLogger('bot.scheduler')

async def sync_all_clans(bot):
    try:
        alerts_to_send = await asyncio.to_thread(run_heavy_sync_task)
        for channel_id, message in alerts_to_send:
            try:
                channel = bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(message)
            except Exception as e:
                logger.error(f"Failed to send alert to {channel_id}: {e}")
    except Exception as e:
        logger.error(f"Critical error spawning sync thread: {e}")

def start_scheduler(bot):
    scheduler = AsyncIOScheduler()
    
    # LOGIKA SMART SYNC (Berdasarkan tanggal)
    # CWL biasanya tgl 1-12. Off-season (war biasa) tgl 13-31.
    today = datetime.datetime.utcnow().day
    
    if 1 <= today <= 12:
        interval_minutes = 15 # CWL Mode: 15 menit sekali
        logger.info("CWL Mode aktif: Sync data tiap 15 menit.")
    else:
        interval_minutes = 180 # Off-season Mode: 3 jam sekali (hemat API)
        logger.info("Off-season Mode aktif: Sync data tiap 3 jam.")

    scheduler.add_job(sync_all_clans, 'interval', minutes=interval_minutes, args=[bot], id='sync_all_clans_job')
    scheduler.start()
