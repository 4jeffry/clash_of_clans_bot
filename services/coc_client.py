import aiohttp
import os
import logging

logger = logging.getLogger('bot.coc')

class CoCClient:
    def __init__(self):
        self.api_token = os.getenv('COC_API_TOKEN')
        self.base_url = 'https://proxy.royaleapi.dev/v1'
        # RoyaleAPI Proxy butuh User-Agent agar tidak kena tembak HTTP 403
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
            'User-Agent': 'ixiera-coc-bot/1.0'
        }

    def _format_tag(self, tag: str) -> str:
        clean_tag = tag.replace('#', '').upper()
        return f"%23{clean_tag}"

    async def get_clan_info(self, clan_tag: str):
        url = f"{self.base_url}/clans/{self._format_tag(clan_tag)}"
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                logger.error(f"Gagal fetch clan info: HTTP {response.status}")
                return None
                
    async def get_current_war(self, clan_tag: str):
        url = f"{self.base_url}/clans/{self._format_tag(clan_tag)}/currentwar"
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('state') == 'notInWar':
                        return None
                    return data
                logger.error(f"Gagal fetch war info: HTTP {response.status}")
                return None
