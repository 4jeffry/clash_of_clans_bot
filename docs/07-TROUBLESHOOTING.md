# Troubleshooting

## Failed to fetch di Web

Penyebab: Backend error (500) atau CORS block.
Solusi: Cek log Railway. Kalau ada error Python, fix di backend.

## NameError: ServerConfig is not defined

Penyebab: Lupa `from models import ServerConfig`.
Solusi: Cek `api/routers/clan.py` bagian import.

## AI Credits selalu 0

Penyebab: `ai_credits` tidak ada di `models.py`.
Solusi: Pakai Raw SQL: `SELECT ai_credits FROM server_configs WHERE guild_id = :gid`.

## Matchmaking War Room kosong

Penyebab: Tag member (`#ABC123`) beda format di DB.
Solusi: Pastikan normalisasi `.replace('#', '')` di query.

## Admin 403 Forbidden

Penyebab: `ADMIN_DISCORD_ID` di Railway salah (masih pakai Guild ID atau ID lain).
Solusi: Ambil User ID Discord (klik kanan profil > Copy User ID), bukan Server ID.

## Build Vercel gagal Could not resolve

Penyebab: File view di-import tapi belum ada.
Solusi: Cek folder `src/views/`, pastikan semua file yang di-import ada.

## Supabase DuplicatePreparedStatement

Penyebab: PgBouncer + SQLAlchemy konflik.
Solusi: Tambahkan `disable_prepare(db)` atau pakai `if_exists` di query.
