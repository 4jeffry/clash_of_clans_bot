# Arsitektur Niki

## Tech Stack

| Layer | Teknologi | Hosting |
|-------|-----------|---------|
| Backend | Python 3.13 + FastAPI | Railway |
| Bot Discord | discord.py | Railway |
| Frontend | Vue 3 + Vite + Tailwind | Vercel |
| Database | PostgreSQL (Supabase) | Supabase |
| AI Engine | Google Gemini | Google API |
| Payment | Manual (via Admin Panel) | - |

## Struktur Folder Backend

~~~text
clan-bot/
├── api/
│   ├── main.py
│   ├── deps.py
│   ├── config.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── clan.py
│   │   ├── ai/
│   │   │   ├── audit.py
│   │   │   ├── war_room.py
│   │   │   ├── war_report.py
│   │   │   ├── cwl_roster.py
│   │   │   ├── cwl_report.py
│   │   │   ├── history.py
│   │   │   └── utils.py
│   │   └── admin/
│   │       ├── auth_utils.py
│   │       ├── dashboard.py
│   │       ├── requests.py
│   │       ├── broadcast.py
│   │       └── stats.py
│   ├── services/
│   │   └── web_ai.py
├── cogs/
│   ├── clan.py
│   ├── war.py
│   ├── members.py
│   ├── capital.py
│   ├── race.py
│   ├── recap.py
│   ├── moderation.py
│   ├── setup.py
│   ├── ai.py
│   └── help.py
├── models.py
├── run_all.py
└── docs/
~~~

## Struktur Folder Frontend

~~~text
niki-bot-web/
├── src/
│   ├── views/
│   │   ├── landing/
│   │   ├── auth/
│   │   ├── app/
│   │   │   ├── DashboardLayout.vue
│   │   │   ├── SettingsView.vue
│   │   │   └── server/
│   │   └── admin/
│   ├── components/
│   │   ├── ui/
│   │   ├── PremiumGate.vue
│   │   └── ...
│   ├── lib/
│   │   ├── api.js
│   │   ├── toast.js
│   │   └── confirm.js
│   ├── router/index.js
│   └── App.vue
~~~
