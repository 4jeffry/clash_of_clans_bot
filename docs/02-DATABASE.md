# Database Schema (Supabase / PostgreSQL)

Catatan: Beberapa tabel di Supabase mungkin dibuat via SQL Editor dan belum direfleksikan di `models.py`. Skema di bawah adalah akumulasi dari `models.py` dan Supabase asli.

## server_configs
| Kolom | Tipe | Keterangan |
|-------|------|------------|
| guild_id | VARCHAR (PK) | ID Server Discord |
| clan_tag | VARCHAR | Tag klan CoC |
| clan_badge_url | TEXT | URL badge klan |
| setup_by | VARCHAR | User ID yang setup |
| tier | VARCHAR | free/standard/pro |
| alert_channel_id | VARCHAR | Channel ID Discord untuk notif |
| ai_credits | INTEGER | Sisa kredit AI (ada di Supabase) |
| expired_at | TIMESTAMP | Tanggal expired tier |
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

## ai_reports
| Kolom | Tipe | Keterangan |
|-------|------|------------|
| id | INTEGER (PK) | |
| clan_tag | VARCHAR | |
| kind | VARCHAR | audit_enhance/war_room/war_report |
| ref_key | VARCHAR | |
| payload | JSONB | Snapshot data input & output AI |
| created_at | TIMESTAMP | |

## members
`tag` (PK), `clan_tag`, `name`, `role`, `townhall_level`, `donations`, `donations_received`, `last_updated`.

## wars
`id` (PK), `clan_tag`, `opponent_tag`, `opponent_name`, `team_size`, `state`, `is_cwl`, `cwl_season_id` (FK), `created_at`, `start_time`, `end_time`, `result`, `clan_stars`, `clan_destruction`, `opp_stars`, `opp_destruction`, `attacks_per_member`.

## war_attacks
`id` (PK), `war_id` (FK), `attacker_tag`, `attacker_name`, `defender_tag`, `stars`, `destruction_percentage`, `order_num`, `attacker_th`, `defender_th`, `attacker_map_position`, `defender_map_position`, `is_fresh_attack`, `net_stars`, `created_at`.

## war_history
`id` (PK), `clan_tag`, `opponent_name`, `opponent_tag`, `result`, `stars`, `destruction_percentage`, `end_time`.

## cwl_seasons
`id` (PK), `month`, `clan_tag`, `created_at`.

## cwl_roster
`id` (PK), `season_id` (FK), `player_tag`, `townhall_level`, `rounds_played`.

## war_participants
`id` (PK), `war_id` (FK), `player_tag`, `player_name`, `townhall_level`, `map_position`, `attacks_used`, `attacks_allowed`, `opp_attacks_count`, `best_opp_stars`, `best_opp_destruction`.

## member_snapshots
`id` (PK), `player_tag`, `clan_tag`, `snap_date`, `townhall_level`, `trophies`, `war_stars`, `war_preference`, `donations`, `donations_received`, `heroes` (JSONB), `equipment` (JSONB).

## race_rewards
`id` (PK), `scope_type`, `scope_id`, `player_tag`, `reward_note`, `claimed_at`.

## capital_raids
`id` (PK), `clan_tag`, `state`, `total_loot`, `total_attacks`, `districts_destroyed`, `defensive_rewards`, `raids_completed`, `created_at`.

## capital_participants
`id` (PK), `raid_id` (FK), `player_tag`, `player_name`, `townhall_level`, `contributions`, `attacks_used`.
