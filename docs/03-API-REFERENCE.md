# API Reference & Payload

Base URL: `https://clashofclansbot-production.up.railway.app`
Auth: `Authorization: Bearer <JWT>`
Tenant: `X-Guild-Id: <guild_id>`

## 1. Auth
### POST /auth/discord
Menukar Discord OAuth `code` menjadi JWT. Backend akan memvalidasi apakah user memiliki permission `MANAGE_GUILD` (0x20) atau `ADMINISTRATOR` (0x8).
**Request Body:**
~~~json
{
  "code": "discord_auth_code_here",
  "redirect_uri": "https://niki-bot-web.vercel.app/auth/callback"
}
~~~
**Response (200 OK):**
~~~json
{
  "access_token": "eyJhbGciOi...",
  "user": {
    "id": "1398959824976478298",
    "username": "AdminNiki",
    "global_name": "Admin",
    "avatar": "hash_avatar"
  },
  "servers": [
    {
      "guild_id": "1234567890",
      "clan_tag": "#ABC123",
      "clan_badge_url": "https://api-assets.clashofclans.com/...",
      "tier": "pro",
      "expired_at": "2026-12-31T23:59:59"
    }
  ]
}
~~~

### GET /auth/me
Mengambil ulang data user dan server dari JWT.
**Response (200 OK):** Sama seperti response di atas (tanpa `access_token`).

## 2. AI
### POST /ai/audit/enhance
Meningkatkan laporan audit rule-based menggunakan Gemini AI. Endpoint ini **tidak menerima Request Body JSON**. Data klan langsung ditarik dari database berdasarkan header `X-Guild-Id`.
**Headers:** `Authorization: Bearer <token>`, `X-Guild-Id: 1234567890`
**Response (200 OK):**
~~~json
{
  "narrative": "AUDIT KESEHATAN KLAN\n1. STATUS UTAMA...",
  "credits": 29
}
~~~
**Response (402 Payment Required):** Jika kredit AI habis.
~~~json
{
  "detail": "Kredit AI Anda habis. Silakan top up."
}
~~~
