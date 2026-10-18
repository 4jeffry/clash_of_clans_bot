# Frontend Guide (Vue)

## Routing

| URL | Komponen | Akses |
|-----|----------|-------|
| `/` | LandingView | Public |
| `/auth/callback` | CallbackView | Public |
| `/app` | DashboardLayout -> HomeView | Auth |
| `/app/server/:guildId/...` | Server views | Auth + Owner |
| `/admin` | AdminLayout -> AdminOverviewView | Admin only |
| `/admin/servers` | AdminServersView | Admin |
| `/admin/requests` | AdminRequestsView | Admin |
| `/admin/broadcast` | AdminBroadcastView | Admin |

## Komponen Reusable

- `lib/api.js` -> `apiFetch(path, options)` - Wrapper fetch (JWT + cache)
- `lib/toast.js` -> `showToast(message, type)` - Toast global
- `lib/confirm.js` -> `showConfirm(message)` - Confirm modal global (return Promise)
- `components/ui/Toast.vue` - Render visual toast
- `components/PremiumGate.vue` - Gembok fitur Pro

## Theming

- Dark Mode: `class="dark"` di `<html>`, pakai prefix `dark:`
- Warna Brand: `bg-brand` (ungu), `bg-brand-dark`, `bg-brand-light`
- Warna Dark: `bg-navy-950` (paling gelap), `bg-navy-900`, `bg-navy-800`
