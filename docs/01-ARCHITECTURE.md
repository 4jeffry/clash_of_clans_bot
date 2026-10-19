# Arsitektur Niki

## Prinsip Utama: Decoupled Architecture (Pemisahan Sistem)
Aplikasi ini didesain dengan prinsip **Decoupled Architecture**. Web API (FastAPI) dan Discord Bot (discord.py) dipisah secara total dan berjalan di *process/service* yang berbeda. 
Tujuan utamanya adalah **Isolasi Beban Kerja**: Aktivitas berat di Web App (seperti *generate* laporan AI atau *fetching* data besar oleh banyak user) tidak akan mengganggu *uptime* dan responsivitas Bot Discord. Keduanya hanya berkomunikasi secara tidak langsung melalui Database (Supabase).

## Tech Stack

| Layer | Teknologi | Hosting |
|-------|-----------|---------|
| Web Backend API | Python 3.13 + FastAPI | Railway (Service 1) |
| Discord Bot | discord.py + APScheduler | Railway (Service 2) |
| Frontend Web | Vue 3 + Vite + Tailwind | Vercel |
| Database | PostgreSQL + SQLAlchemy | Supabase |
| AI Engine | Google Gemini (google-genai) | Google API |
| Reporting | ReportLab + Matplotlib | Server/Local |

## Struktur Folder Backend (`~/clan-bot`)

~~~text
clan-bot/
├── api/                    # [WEB API] Khusus untuk FastAPI Web Server
│   ├── main.py             # Entry point API (app = FastAPI())
│   ├── deps.py             # Dependency (get_db, JWT auth)
│   ├── config.py           # Konfigurasi env
│   ├── routers/            # Kumpulan Endpoint
│   │   ├── auth.py         # Endpoint Login OAuth Discord
│   │   ├── clan.py         # Endpoint data klan & server
│   │   ├── ai/             # Endpoint fitur AI Web
│   │   │   ├── audit.py
│   │   │   ├── cwl_report.py
│   │   │   ├── cwl_roster.py
│   │   │   ├── history.py
│   │   │   ├── utils.py
│   │   │   ├── war_report.py
│   │   │   └── war_room.py
│   │   └── admin/          # Endpoint Admin Panel
│   │       ├── analytics.py
│   │       ├── auth_utils.py
│   │       ├── broadcast.py
│   │       ├── dashboard.py
│   │       ├── requests.py
│   │       └── stats.py
│   └── services/
│       └── web_ai.py       # Logic AI khusus web
├── cogs/                   # [BOT] Khusus untuk Discord.py
│   ├── ai.py               # Command /ai
│   ├── capital.py          # Command /capital
│   ├── clan.py             # Command /clanmembers
│   ├── help.py             # Command /help
│   ├── members.py          # Command member/donasi
│   ├── moderation.py       # Command moderasi
│   ├── race.py             # Command race
│   ├── recap.py            # Command recap
│   ├── setup.py            # Command /setup
│   └── war.py              # Command war
├── services/               # [SHARED] Logic yang dipakai Web & Bot
│   ├── coc_client.py       # Fetch API Clash of Clans
│   ├── db.py               # Koneksi Database
│   ├── llm_client.py       # Wrapper Gemini AI
│   └── sync_worker.py      # Worker sinkronisasi data background
├── src/
│   └── composables/
│       └── useTheme.js
├── models.py               # [SHARED] Skema ORM SQLAlchemy
├── bot.py                  # [BOT] Entry point Bot
├── scheduler.py            # [BOT] Cron job (auto-sync)
├── run_all.py              # [RUNNER] Jalanin API & Bot bareng (dev)
├── Procfile                # Konfigurasi Deploy Railway
├── requirements.txt        # Dependencies
└── docs/                   # Dokumentasi (folder ini)
~~~

## Struktur Folder Frontend (`~/niki-bot-web`)

~~~text
niki-bot-web/
├── src/
│   ├── App.vue
│   ├── main.js
│   ├── style.css
│   ├── components/
│   │   ├── Documentation.vue
│   │   ├── Features.vue
│   │   ├── Footer.vue
│   │   ├── Hero.vue
│   │   ├── MemberStatsModal.vue
│   │   ├── Navbar.vue
│   │   ├── PremiumGate.vue
│   │   ├── icons/
│   │   │   ├── IconCapitalGold.vue
│   │   │   ├── IconRaidMedal.vue
│   │   │   ├── IconStar.vue
│   │   │   └── IconWar.vue
│   │   └── ui/
│   │       ├── CustomSelect.vue
│   │       ├── EditRewardModal.vue
│   │       ├── SearchInput.vue
│   │       └── Toast.vue
│   ├── composables/
│   │   ├── useAuth.js
│   │   └── useTheme.js
│   ├── lib/
│   │   ├── api.js          # Fetch wrapper (JWT, X-Guild-Id, Cache)
│   │   ├── assets.js
│   │   ├── confirm.js
│   │   └── toast.js
│   ├── router/
│   │   └── index.js
│   └── views/
│       ├── admin/
│       │   ├── AdminBroadcastView.vue
│       │   ├── AdminLayout.vue
│       │   ├── AdminOverviewView.vue
│       │   ├── AdminRequestsView.vue
│       │   └── AdminServersView.vue
│       ├── app/
│       │   ├── DashboardLayout.vue
│       │   ├── HomeView.vue
│       │   ├── SettingsView.vue
│       │   └── server/
│       │       ├── AiAuditView.vue
│       │       ├── AiHistoryView.vue
│       │       ├── AiReportView.vue
│       │       ├── AiWarReportView.vue
│       │       ├── AiWarRoomView.vue
│       │       ├── CapitalView.vue
│       │       ├── CompareView.vue
│       │       ├── CwlRosterView.vue
│       │       ├── CwlView.vue
│       │       ├── DonationsView.vue
│       │       ├── InactiveView.vue
│       │       ├── LeaderboardView.vue
│       │       ├── MembersLayout.vue
│       │       ├── MembersView.vue
│       │       ├── RaceCwlView.vue
│       │       ├── RaceWarView.vue
│       │       ├── RecapCwlView.vue
│       │       ├── RecapWarView.vue
│       │       ├── RewardsView.vue
│       │       ├── ServerHomeView.vue
│       │       ├── ServerLayout.vue
│       │       ├── ThCompositionView.vue
│       │       ├── WarLayout.vue
│       │       └── WarView.vue
│       ├── auth/
│       │   └── CallbackView.vue
│       └── landing/
│           └── LandingView.vue
├── index.html
├── package.json
├── postcss.config.js
├── tailwind.config.js
└── vite.config.js
~~~

## Alur Komunikasi
1. **Web Flow**: Frontend (Vue) -> Request HTTP -> API (`api/`) -> Database / Gemini AI.
2. **Bot Flow**: Discord User -> Slash Command -> Bot (`cogs/`) -> Database / Gemini AI.
3. **Shared State**: Jika Web mengubah data (misal *update config server*), Bot akan membacanya dari Database saat command dipanggil.
