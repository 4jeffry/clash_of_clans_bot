# Database Schema (Supabase)

Dokumen ini adalah sumber kebenaran (source of truth) struktur database Niki. Menggabungkan tabel dari Bot Discord dan Web App.

## Ringkasan Relasi (Foreign Keys)
- `wars.cwl_season_id` -> `cwl_seasons.id`
- `war_attacks.war_id` -> `wars.id`
- `war_participants.war_id` -> `wars.id`
- `cwl_roster.season_id` -> `cwl_seasons.id`
- `capital_participants.raid_id` -> `capital_raids.id`

---

## 1. server_configs
Menyimpan pengaturan server Discord dan status tier/langganan.

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| guild_id | varchar | NO | - | Primary Key |
| clan_tag | varchar | NO | - | |
| clan_badge_url | text | YES | - | |
| setup_by | varchar | YES | - | |
| tier | varchar | YES | 'free' | |
| alert_channel_id | varchar | YES | - | |
| ai_credits | integer | YES | 30 | |
| expired_at | timestamp | YES | - | |
| created_at | timestamp | YES | - | |

## 2. members
Data member klan saat ini (di-sync dari API CoC).

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| tag | varchar | NO | - | Primary Key |
| clan_tag | varchar | NO | - | |
| name | varchar | NO | - | |
| role | varchar | YES | - | |
| townhall_level | integer | YES | - | |
| donations | integer | YES | - | |
| donations_received| integer | YES | - | |
| last_updated | timestamp | YES | - | |

## 3. analytics_events
Tracking event untuk halaman web (Admin Panel / Web App).

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| path | varchar | NO | - | |
| user_id | varchar | YES | - | |
| guild_id | varchar | YES | - | |
| event_type | varchar | YES | 'page_view' | |
| created_at | timestamp | YES | now() | |

## 4. upgrade_requests
Antrean request upgrade tier dari user ke Admin.

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| guild_id | varchar | NO | - | |
| clan_tag | varchar | YES | - | |
| requested_tier | varchar | YES | 'pro' | |
| status | varchar | YES | 'pending' | |
| created_at | timestamp | YES | now() | |

## 5. ai_reports
Menyimpan riwayat prompt dan hasil dari Gemini AI.

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | uuid | NO | gen_random_uuid()| Primary Key |
| guild_id | varchar | NO | - | |
| feature_type | varchar | NO | - | |
| input_data | jsonb | YES | - | |
| result_narrative| text | YES | - | |
| created_at | timestamp | YES | now() | |

## 6. war_history
Rekap hasil akhir per perang.

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| clan_tag | varchar | NO | - | |
| opponent_name | varchar | YES | - | |
| opponent_tag | varchar | YES | - | |
| result | varchar | YES | - | |
| stars | integer | YES | - | |
| destruction_percentage| integer | YES | - | |
| end_time | timestamp | YES | - | |

## 7. wars
Detail perang klan (reguler & CWL).

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| clan_tag | varchar(20) | NO | - | |
| opponent_tag | varchar(20) | YES | - | |
| opponent_name | varchar(100) | YES | - | |
| team_size | integer | YES | - | |
| state | varchar(20) | YES | - | |
| is_cwl | boolean | YES | false | |
| cwl_season_id | integer | YES | - | Foreign Key -> cwl_seasons.id |
| created_at | timestamp | YES | - | |
| start_time | timestamp | YES | - | |
| end_time | timestamp | YES | - | |
| result | varchar(10) | YES | - | |
| clan_stars | integer | YES | - | |
| clan_destruction | numeric(5,2) | YES | - | |
| opp_stars | integer | YES | - | |
| opp_destruction | numeric(5,2) | YES | - | |
| attacks_per_member| integer | YES | - | |

## 8. war_attacks
Log serangan per pemain dalam perang.

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| war_id | integer | YES | - | Foreign Key -> wars.id |
| attacker_tag | varchar(20) | NO | - | Unique(war_id, attacker_tag, order_num) |
| attacker_name | varchar(100) | NO | - | |
| defender_tag | varchar(20) | YES | - | |
| stars | integer | YES | 0 | |
| destruction_percentage| integer| YES | 0 | |
| order_num | integer | YES | 1 | Unique constraint |
| attacker_th | integer | YES | 0 | |
| defender_th | integer | YES | 0 | |
| attacker_map_position| integer | YES | 0 | |
| defender_map_position| integer | YES | 0 | |
| is_fresh_attack | boolean | YES | true | |
| net_stars | integer | YES | 0 | |
| created_at | timestamp | YES | now() | |

## 9. war_participants
Daftar peserta perang beserta statistiknya.

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| war_id | integer | NO | - | Foreign Key -> wars.id |
| player_tag | varchar(20) | NO | - | Unique(war_id, player_tag) |
| player_name | varchar(100) | YES | - | |
| townhall_level | integer | YES | - | |
| map_position | integer | YES | - | |
| attacks_used | integer | YES | - | |
| attacks_allowed | integer | YES | - | |
| opp_attacks_count | integer | YES | - | |
| best_opp_stars | integer | YES | - | |
| best_opp_destruction| numeric(5,2) | YES | - | |

## 10. war_opponents
Cache data lawan (Web App).

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| war_id | integer | YES | - | |
| player_tag | varchar | YES | - | |
| player_name | varchar | YES | - | |
| townhall_level | integer | YES | - | |
| map_position | integer | YES | - | |
| best_stars | integer | YES | - | |
| created_at | timestamp | YES | - | |

## 11. cwl_seasons
Penanda musim CWL.

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| month | varchar(7) | NO | - | |
| clan_tag | varchar(20) | NO | - | |
| created_at | timestamp | YES | now() | |

## 12. cwl_roster
Daftar pemain yang ikut CWL di musim tertentu.

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| season_id | integer | NO | - | Foreign Key -> cwl_seasons.id |
| player_tag | varchar(20) | NO | - | Unique(season_id, player_tag) |
| townhall_level | integer | YES | - | |
| rounds_played | integer | YES | 0 | |

## 13. member_snapshots
Snapshot harian member untuk tracking progress.

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| player_tag | varchar(20) | NO | - | Unique(player_tag, snap_date) |
| clan_tag | varchar(20) | NO | - | |
| snap_date | date | NO | CURRENT_DATE| |
| townhall_level | integer | YES | - | |
| trophies | integer | YES | - | |
| war_stars | integer | YES | - | |
| war_preference | varchar(10) | YES | - | |
| donations | integer | YES | - | |
| donations_received| integer | YES | - | |
| heroes | jsonb | YES | - | |
| equipment | jsonb | YES | - | |

## 14. race_rewards
Tracking reward untuk event Race (jika ada).

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| scope_type | varchar(10) | NO | - | |
| scope_id | integer | NO | - | |
| player_tag | varchar(20) | NO | - | |
| reward_note | text | YES | - | |
| claimed_at | timestamp | YES | now() | |

## 15. capital_raids
Data Raid Weekend (Capital).

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| clan_tag | varchar(20) | NO | - | |
| state | varchar(20) | YES | - | |
| total_loot | bigint | YES | - | |
| total_attacks | integer | YES | - | |
| districts_destroyed| integer | YES | - | |
| defensive_rewards | bigint | YES | - | |
| raids_completed | integer | YES | - | |
| created_at | timestamp | YES | now() | |

## 16. capital_participants
Data kontribusi pemain per Raid Weekend.

| Kolom | Tipe Data | Null | Default | Keterangan |
|-------|-----------|------|---------|------------|
| id | integer | NO | nextval(...) | Primary Key |
| raid_id | integer | YES | - | Foreign Key -> capital_raids.id |
| player_tag | varchar(20) | NO | - | |
| player_name | varchar(100) | YES | - | |
| townhall_level | integer | YES | - | |
| contributions | bigint | YES | - | |
| attacks_used | integer | YES | - | |
