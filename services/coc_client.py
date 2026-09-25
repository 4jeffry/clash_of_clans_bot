import aiohttp
import os
import logging

logger = logging.getLogger('bot.coc')

class CoCClient:
    def __init__(self):
        # KEMBALI MENGGUNAKAN COCPROXY
        self.base_url = 'https://cocproxy.royaleapi.dev/v1'

    def _format_tag(self, tag: str) -> str:
        clean_tag = tag.replace('#', '').strip().upper()
        return f"%23{clean_tag}"

    def _get_headers(self):
        token = os.getenv('COC_API_TOKEN', '').strip()
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'User-Agent': 'ixiera-coc-bot/1.0'
        }

    async def get_clan_info(self, clan_tag: str):
        if not clan_tag:
            logger.error("CLAN_TAG kosong di environment variable.")
            return None

        url = f"{self.base_url}/clans/{self._format_tag(clan_tag)}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_headers()) as response:
                if response.status == 200:
                    return await response.json()
                
                error_text = await response.text()
                logger.error(f"[CoC API Error] Status: {response.status} | URL: {url} | Detail: {error_text}")
                return None
                
    async def get_current_war(self, clan_tag: str):
        if not clan_tag:
            logger.error("CLAN_TAG kosong di environment variable.")
            return None

        url = f"{self.base_url}/clans/{self._format_tag(clan_tag)}/currentwar"
        
        async with aiohttp.ClientSession(headers=self._get_headers()) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('state') == 'notInWar':
                        return None
                    return data
                
                error_text = await response.text()
                logger.error(f"[CoC API Error War] Status: {response.status} | URL: {url} | Detail: {error_text}")
                return None
