# Deployment

## Backend (Railway)

1. Push code ke GitHub `solvixjfa/clash_of_clans_bot`
2. Railway auto-deploy dari branch `main`
3. Environment Variables wajib:
   - `DATABASE_URL` - Connection string Supabase
   - `DISCORD_TOKEN` - Token bot Discord
   - `COC_API_TOKEN` - API key Clash of Clans
   - `GEMINI_API_KEY` - API key Google Gemini
   - `JWT_SECRET` - Secret JWT (acak)
   - `ADMIN_DISCORD_ID` - Discord ID admin (super admin)

## Frontend (Vercel)

1. Push code ke GitHub `solvixjfa/niki-bot-web`
2. Vercel auto-deploy
3. Environment Variables:
   - `VITE_API_URL` - URL backend Railway
   - `VITE_DISCORD_CLIENT_ID` - OAuth Client ID

## Auto-Deploy

Setiap `git push` ke `main` trigger deploy otomatis di Railway & Vercel.
