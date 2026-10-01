import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import fungsi berat dari file worker terpisah
from services.sync_worker import run_heavy_sync_task

logger = logging.getLogger('bot.scheduler')

async def sync_all_clans(bot):
    try:
        # Lempar semua operasi berat (HTTP API + DB Sync) ke thread terpisah
        alerts_to_send = await asyncio.to_thread(run_heavy_sync_task)
        
        # Kirim notifikasi kembali ke channel Discord (bebas dari blocking!)
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
    scheduler.add_job(sync_all_clans, 'interval', minutes=10, args=[bot], id='sync_all_clans_job')
    scheduler.start()
    logger.info("Scheduler aktif (Interval: 10 Menit, Non-Blocking).")
    asyncio.create_task(sync_all_clans(bot))
