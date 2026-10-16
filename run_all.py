import os
import threading
import logging
import uvicorn
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("run_all")

from api.main import app as api_app

def run_api():
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Starting API server on port {port}")
    uvicorn.run(api_app, host="0.0.0.0", port=port, log_level="info")

def run_bot():
    import discord
    from discord.ext import commands
    from services.db import init_db
    from scheduler import start_scheduler

    TOKEN = os.getenv("DISCORD_TOKEN")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    class ClanBot(commands.Bot):
        def __init__(self):
            super().__init__(command_prefix="!", intents=intents, help_command=None)

        async def setup_hook(self):
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py') and not filename.startswith('__'):
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        logger.info(f'Loaded cog: {filename}')
                    except Exception as e:
                        logger.error(f'Failed to load cog {filename}: {e}')

        async def on_ready(self):
            logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
            init_db()
            start_scheduler(self)
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Clan Wars | /help"))
            try:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands.")
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")

    if not TOKEN:
        logger.error("DISCORD_TOKEN not set!")
        return

    bot = ClanBot()
    bot.run(TOKEN)


if __name__ == "__main__":
    # Start API in background thread
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    logger.info("API thread started")

    # Run bot in main thread
    run_bot()
