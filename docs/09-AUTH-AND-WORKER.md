# Autentikasi & Background Worker

## 1. Alur Autentikasi (OAuth2 & JWT)
Sistem menggunakan Discord OAuth2 untuk autentikasi dan otorisasi berbasis permission server.

1. **Frontend Request**: Frontend mengirim `code` dan `redirect_uri` ke endpoint `POST /auth/discord`.
2. **Token Exchange**: Backend FastAPI menukar `code` dengan Discord API untuk mendapatkan `access_token`.
3. **Fetch Data**: Backend mengambil profil user (`/users/@me`) dan daftar server (`/users/@me/guilds`).
4. **Validasi Permission**: Backend memvalidasi permission user di setiap server menggunakan *bitmask* (`0x20` untuk Manage Server atau `0x8` untuk Administrator).
5. **Generate JWT**: Jika user punya akses, Backend mencari data klan di database. JWT dibuat berisi: `sub` (User ID), `username`, `avatar`, `servers` (list ID server yang di-manage), dan `exp`. Token ini di-sign pakai `JWT_SECRET`.
6. **Auto Fetch Badge**: Jika `clan_badge_url` di database kosong, backend otomatis nembak API Clash of Clans untuk mengambil logo klan dan menyimpannya.

## 2. Scheduler (Smart Sync)
File `scheduler.py` menggunakan `AsyncIOScheduler`. Sistem ini sangat pintar dalam menghemat kuota API Supercell dengan mendeteksi tanggal:

- **CWL Mode (Tanggal 1 - 12)**: Sinkronisasi berjalan setiap **15 menit** sekali.
- **Off-Season Mode (Tanggal 13 - 31)**: Sinkronisasi berjalan setiap **180 menit (3 jam)** sekali.

## 3. Background Worker (`sync_worker.py`)
Worker berjalan di *thread* terpisah agar tidak memblokir bot Discord. Tugas yang dilakukan:

1. **Reset Expired Tier**: Mengecek `ServerConfig`, jika `expired_at` sudah lewat, otomatis turunkan tier ke `free`.
2. **Member Sync**: Mengambil data member dari API CoC. Member yang keluar dari klan otomatis dihapus dari DB dan dikirim notifikasi ke channel alert.
3. **Daily Snapshot**: Membuat rekam jejak (snapshot) harian untuk maksimal 20 member per *run* (mencegah *rate limit*).
4. **Private War Log Alert**: Jika API CoC merespons 403 (War Log Private), bot otomatis mengirim pesan ke Discord menyuruh Leader/Co-Leader membuka setting War Log.
5. **Auto War Alert**: Jika perang sisa < 2 jam dan ada member yang belum menghabiskan serangan, bot mengirim pesan tag ke channel.
6. **War Log & Attack Analysis**: 
   - Membuat/mengupdate data `War`, `WarParticipant`, `WarAttack`.
   - Menghitung `is_fresh_attack` dan `net_stars` (menghitung serangan *cleanup*).
   - Otomatis mendeteksi apakah perang tersebut CWL atau War biasa.
