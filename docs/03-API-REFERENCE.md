# API Reference

Base URL: `https://clashofclansbot-production.up.railway.app`
Auth: `Authorization: Bearer <JWT>` (dari Discord OAuth)
Tenant: `X-Guild-Id: <guild_id>` (header wajib untuk endpoint clan/ai)

## Auth

- `GET /auth/me` - Data user + daftar server

## Clan

- `GET /clan/members` - Daftar member
- `GET /clan/war` - Status war saat ini
- `GET /clan/war/history` - 10 war terakhir
- `GET /clan/capital` - Info raid weekend
- `GET /clan/dashboard` - Stats untuk Dashboard
- `GET /clan/settings` - Config server
- `PUT /clan/settings` - Update alert_channel_id
- `POST /clan/settings/request-upgrade?tier=pro` - Ajukan upgrade

## AI

- `GET /ai/audit` - Laporan rule-based
- `POST /ai/audit/enhance` - Enhance pakai Gemini (potong 1 kredit)
- `GET /ai/war-room` - Matchmaking war
- `POST /ai/war-room/enhance` - Taktik AI war
- `GET /ai/war-report` - Report pasca war
- `POST /ai/war-report/enhance` - Evaluasi AI pasca war
- `GET /ai/cwl-roster` - Generate roster CWL
- `GET /ai/cwl-report` - Statistik CWL
- `GET /ai/history` - List history
- `GET /ai/history/{id}` - Detail history
- `DELETE /ai/history/{id}` - Hapus history

## Admin (khusus ADMIN_DISCORD_ID)

- `GET /admin/stats` - Statistik global
- `GET /admin/servers` - Semua server
- `PUT /admin/servers/{guild_id}` - Update tier/credits/expired
- `GET /admin/upgrade-requests` - Antrean upgrade
- `DELETE /admin/upgrade-requests/{id}` - Hapus request
- `POST /admin/broadcast` - Kirim promo ke semua channel
