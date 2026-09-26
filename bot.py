import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging

from services.db import init_db
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bot')

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

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

        # SYNC SLASH COMMANDS KE DISCORD
        try:
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} Slash Commands.")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

    async def on_ready(self):
        logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
        logger.info('------')
        
        init_db()
        start_scheduler()
        
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Clan Wars | /help"))

if __name__ == '__main__':
    if not TOKEN:
        logger.error("DISCORD_TOKEN tidak ditemukan di file .env!")
    else:
        bot = ClanBot()
        bot.run(TOKEN)
