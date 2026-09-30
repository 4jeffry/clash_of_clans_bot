from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Date, Numeric, UniqueConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import JSONB
import datetime

Base = declarative_base()

class ServerConfig(Base):
    __tablename__ = 'server_configs'
    guild_id = Column(String, primary_key=True)
    clan_tag = Column(String, nullable=False)
    setup_by = Column(String)
    tier = Column(String, default="free")
    alert_channel_id = Column(String, nullable=True)
    expired_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ClanMember(Base):
    __tablename__ = 'members'
    tag = Column(String, primary_key=True)
    clan_tag = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String)
    townhall_level = Column(Integer)
    donations = Column(Integer, default=0)
    donations_received = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

class WarHistory(Base):
    __tablename__ = 'war_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    clan_tag = Column(String, nullable=False)
    opponent_name = Column(String)
    opponent_tag = Column(String)
    result = Column(String)
    stars = Column(Integer)
    destruction_percentage = Column(Integer)
    end_time = Column(DateTime, default=datetime.datetime.utcnow)

class War(Base):
    __tablename__ = 'wars'
    id = Column(Integer, primary_key=True, autoincrement=True)
    clan_tag = Column(String(20), nullable=False)
    opponent_tag = Column(String(20))
    opponent_name = Column(String(100))
    team_size = Column(Integer, default=0)
    state = Column(String(20))
    is_cwl = Column(Boolean, default=False)
    cwl_season_id = Column(Integer, ForeignKey('cwl_seasons.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Kolom Baru (Update Fase 1)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    result = Column(String(10), nullable=True)
    clan_stars = Column(Integer, nullable=True)
    clan_destruction = Column(Numeric(5, 2), nullable=True)
    opp_stars = Column(Integer, nullable=True)
    opp_destruction = Column(Numeric(5, 2), nullable=True)
    attacks_per_member = Column(Integer, default=2)

class WarAttack(Base):
    __tablename__ = 'war_attacks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    war_id = Column(Integer, ForeignKey('wars.id', ondelete='CASCADE'))
    attacker_tag = Column(String(20), nullable=False)
    attacker_name = Column(String(100), nullable=False)
    defender_tag = Column(String(20))
    stars = Column(Integer, default=0)
    destruction_percentage = Column(Integer, default=0)
    order_num = Column(Integer, default=1)
    
    attacker_th = Column(Integer, default=0)
    defender_th = Column(Integer, default=0)
    attacker_map_position = Column(Integer, default=0)
    defender_map_position = Column(Integer, default=0)
    is_fresh_attack = Column(Boolean, default=True)
    net_stars = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('war_id', 'attacker_tag', 'order_num', name='war_attacks_uniq'),
    )

class CWLSeason(Base):
    __tablename__ = 'cwl_seasons'
    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(String(7), nullable=False)
    clan_tag = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class RaceReward(Base):
    __tablename__ = 'race_rewards'
    id = Column(Integer, primary_key=True, autoincrement=True)
    scope_type = Column(String(10), nullable=False)
    scope_id = Column(Integer, nullable=False)
    player_tag = Column(String(20), nullable=False)
    reward_note = Column(Text, nullable=True)
    claimed_at = Column(DateTime, default=datetime.datetime.utcnow)

# ==========================================
# TABEL BARU FASE 1 (PRO / AI FOUNDATION)
# ==========================================

class WarParticipant(Base):
    __tablename__ = 'war_participants'
    id = Column(Integer, primary_key=True, autoincrement=True)
    war_id = Column(Integer, ForeignKey('wars.id', ondelete='CASCADE'), nullable=False)
    player_tag = Column(String(20), nullable=False)
    player_name = Column(String(100))
    townhall_level = Column(Integer)
    map_position = Column(Integer)
    attacks_used = Column(Integer, default=0)
    attacks_allowed = Column(Integer, default=2)

    __table_args__ = (
        UniqueConstraint('war_id', 'player_tag', name='uq_war_participant'),
    )

class MemberSnapshot(Base):
    __tablename__ = 'member_snapshots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_tag = Column(String(20), nullable=False)
    clan_tag = Column(String(20), nullable=False)
    snap_date = Column(Date, nullable=False, default=datetime.date.today)
    townhall_level = Column(Integer)
    trophies = Column(Integer)
    war_stars = Column(Integer)
    war_preference = Column(String(10))
    donations = Column(Integer)
    donations_received = Column(Integer)
    heroes = Column(JSONB)     # Membutuhkan psycopg2 / psycopg binary untuk JSONB
    equipment = Column(JSONB)

    __table_args__ = (
        UniqueConstraint('player_tag', 'snap_date', name='uq_member_snapshot'),
    )

class CWLRoster(Base):
    __tablename__ = 'cwl_roster'
    id = Column(Integer, primary_key=True, autoincrement=True)
    season_id = Column(Integer, ForeignKey('cwl_seasons.id', ondelete='CASCADE'), nullable=False)
    player_tag = Column(String(20), nullable=False)
    townhall_level = Column(Integer)
    rounds_played = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint('season_id', 'player_tag', name='uq_cwl_roster'),
    )

class AIReport(Base):
    __tablename__ = 'ai_reports'
    id = Column(Integer, primary_key=True, autoincrement=True)
    clan_tag = Column(String(20), nullable=False)
    kind = Column(String(30), nullable=False)
    ref_key = Column(String(60))
    payload = Column(JSONB)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('clan_tag', 'kind', 'ref_key', name='uq_ai_report'),
    )
