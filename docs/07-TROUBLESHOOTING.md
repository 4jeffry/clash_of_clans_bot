# Troubleshooting

## Failed to fetch di Web
Penyebab: Backend error (500) atau CORS block.
Solusi: Cek log Railway. Kalau ada error Python, fix di backend.

## NameError: ServerConfig is not defined
Penyebab: Lupa `from models import ServerConfig`.
Solusi: Cek import di file router terkait.

## AI Credits selalu 0
Penyebab: `ai_credits` tidak ada di `models.py` (SQLAlchemy model).
Solusi: Karena kolom ini ada di Supabase, pastikan backend menggunakan Raw SQL (`SELECT ai_credits FROM server_configs WHERE guild_id = :gid`) atau tambahkan kolomnya ke `models.py`.

## Matchmaking War Room kosong
Penyebab: Tag member (`#ABC123`) beda format di DB.
Solusi: Pastikan normalisasi `.replace('#', '')` di query.

## Admin 403 Forbidden
Penyebab: `ADMIN_DISCORD_ID` di Railway salah.
Solusi: Gunakan User ID Discord, bukan Server ID.

## Supabase DuplicatePreparedStatement
Penyebab: PgBouncer + SQLAlchemy konflik.
Solusi: Tambahkan `disable_prepare(db)` atau gunakan transaction mode yang sesuai.
