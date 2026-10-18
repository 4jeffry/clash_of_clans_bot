# Frontend Guide (Vue 3)

## Tech Stack
- Framework: Vue 3 (Composition API)
- Build Tool: Vite
- Styling: Tailwind CSS
- State/Routing: Vue Router 4, Composables (`useAuth`, `useTheme`)
- Charts: Chart.js + Vue-Chartjs
- Tracking: Custom API track (`/admin/track`) + Umami (`window.umami`)

## Struktur Folder `src`
~~~text
src/
├── App.vue
├── main.js
├── style.css
├── assets/            # (jika ada)
├── components/
│   ├── Documentation.vue
│   ├── Features.vue
│   ├── Footer.vue
│   ├── Hero.vue
│   ├── MemberStatsModal.vue
│   ├── Navbar.vue
│   ├── PremiumGate.vue
│   ├── icons/         # IconCapitalGold, IconRaidMedal, IconStar, IconWar
│   └── ui/            # CustomSelect, EditRewardModal, SearchInput, Toast
├── composables/
│   ├── useAuth.js
│   └── useTheme.js
├── lib/
│   ├── api.js         # Fetch wrapper + Cache (2 menit)
│   ├── assets.js
│   ├── confirm.js
│   └── toast.js
├── router/
│   └── index.js
└── views/
    ├── admin/         # AdminLayout, Overview, Servers, Requests, Broadcast
    ├── app/           # DashboardLayout, Home, Settings
    │   └── server/    # Rute bersarang (War, Members, Capital, AI)
    ├── auth/          # CallbackView
    └── landing/       # LandingView
~~~

## Routing (Vue Router)
Router menggunakan mode `createWebHistory`. Beberapa grup rute bersarang (nested) menggunakan `Layout` tersendiri.

| Path | Komponen | Akses |
|------|----------|-------|
| `/` | LandingView | Public |
| `/auth/callback` | CallbackView | Public |
| `/app` | DashboardLayout | Auth |
| `/app/server/:guildId` | ServerLayout | Auth + Guild Context |
| `/app/server/:guildId/war/...` | WarLayout (Status, CWL, Race, Recap, dll) | Auth |
| `/app/server/:guildId/members/...`| MembersLayout (List, Donations, Inactive, dll)| Auth |
| `/app/server/:guildId/ai-...` | AiAudit, AiWarRoom, AiWarReport, AiHistory | Auth |
| `/admin` | AdminLayout | Admin Only |
| `/admin/servers` | AdminServersView | Admin Only |
| `/admin/requests` | AdminRequestsView | Admin Only |
| `/admin/broadcast` | AdminBroadcastView | Admin Only |

**Route Guard (`router.beforeEach`)**:
- Cek `localStorage.getItem('niki_token')`. Jika rute butuh auth dan token kosong, tendang ke `/`.
- **Admin Bypass**: Di `router.afterEach`, dilakukan *decode* JWT. Jika `user_id` cocok dengan Admin ID, tracking API dan Umami di-*skip* (biar statistik bersih dari aktivitas admin).

## API Wrapper (`src/lib/api.js`)
Wrapper fetch kustom dengan fitur:
- **Auth Header**: Otomatis menyisipkan `Authorization: Bearer <token>` dan `X-Guild-Id`.
- **In-Memory Cache**: Menyimpan respons GET selama 2 menit (kecuali endpoint `/auth/me`). Cache key-nya digabung dengan `guildId` agar data antar server tidak tertukar.
- **401 Handler**: Jika backend mengembalikan 401, otomatis hapus token & data user di `localStorage`, lalu lempar ke landing page.

## Theming
- **Dark Mode**: Menggunakan class `dark` di elemen `<html>` (dikelola oleh `useTheme.js`).
- **Warna Brand**: `bg-brand` (ungu), `bg-brand-dark`, `bg-brand-light`.
- **Warna Dark**: `bg-navy-950`, `bg-navy-900`, `bg-navy-800`.
