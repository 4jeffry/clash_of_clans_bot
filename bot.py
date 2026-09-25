import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging

# Import dari file lokal lu
from services.db import init_db
from scheduler import start_scheduler

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bot')

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('COMMAND_PREFIX', '!')

# Setup Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Penting untuk tracking member Discord

class ClanBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=commands.DefaultHelpCommand())
        
    async def setup_hook(self):
        # Load semua module di folder cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f'Loaded cog: {filename}')
                except Exception as e:
                    logger.error(f'Failed to load cog {filename}: {e}')

    async def on_ready(self):
        logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
        logger.info('------')
        
        # Eksekusi inisialisasi Database saat bot menyala
        init_db()
        
        # Jalankan background scheduler untuk sinkronisasi otomatis
        start_scheduler()
        
        # Set status bot
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Clan Wars"))

if __name__ == '__main__':
    if not TOKEN:
        logger.error("DISCORD_TOKEN tidak ditemukan di file .env!")
    else:
        bot = ClanBot()
        bot.run(TOKEN)
