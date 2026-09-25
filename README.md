# ixiera.id Clan Bot

Bot Discord untuk manajemen ekosistem Clash of Clans, terintegrasi dengan data analitik dan asisten AI.

## Fitur Utama
- Sinkronisasi API CoC via RoyaleAPI Proxy
- Analitik Performa Member & Status War
- Asisten AI (Gemini Flash)
- Penyimpanan Historis (PostgreSQL / SQLite)

## Deployment (Railway)
1. Hubungkan repo ke Railway.
2. Set Environment Variables (`DISCORD_TOKEN`, `COC_API_TOKEN`, `CLAN_TAG`, `GEMINI_API_KEY`, `DATABASE_URL`).
3. Railway akan menggunakan `Procfile` untuk menjalankan bot sebagai _worker_.
