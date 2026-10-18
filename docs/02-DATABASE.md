# Database Schema (Supabase)

Semua tabel di schema `public`.

## server_configs

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| guild_id | VARCHAR (PK) | ID Server Discord |
| clan_tag | VARCHAR | Tag klan CoC |
| clan_badge_url | TEXT | URL badge klan |
| setup_by | VARCHAR | User ID yang setup |
| tier | VARCHAR | free/standard/pro |
| expired_at | TIMESTAMP | Tanggal expired tier |
| alert_channel_id | VARCHAR | Channel ID Discord untuk notif |
| ai_credits | INTEGER | Sisa kredit AI |
| created_at | TIMESTAMP | |

## members

Kolom: `tag`, `clan_tag`, `name`, `role`, `townhall_level`, `donations`, `donations_received`, `last_updated`

## wars

Kolom: `id`, `clan_tag`, `opponent_tag`, `state`, `team_size`, `clan_stars`, `opp_stars`, `is_cwl`, `result`

## ai_reports

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| id | UUID (PK) | |
| guild_id | VARCHAR | Multi-tenant |
| feature_type | VARCHAR | audit_enhance/war_room/war_report |
| input_data | JSONB | Snapshot data input |
| result_narrative | TEXT | Output AI (narasi) |
| created_at | TIMESTAMP | |

## upgrade_requests

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| id | SERIAL (PK) | |
| guild_id | VARCHAR | |
| clan_tag | VARCHAR | |
| requested_tier | VARCHAR | standard/pro |
| status | VARCHAR | pending/approved |
| created_at | TIMESTAMP | |

## war_opponents

Cache matchmaking War Room. Kolom: `id`, `war_id`, `player_tag`, `player_name`, `townhall_level`, `map_position`, `best_stars`, `created_at`
