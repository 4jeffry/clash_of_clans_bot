from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base
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
    
    # Kolom Analitik Kompetitif (Esports Grade)
    attacker_th = Column(Integer, default=0)
    defender_th = Column(Integer, default=0)
    attacker_map_position = Column(Integer, default=0)
    defender_map_position = Column(Integer, default=0)
    is_fresh_attack = Column(Boolean, default=True)
    net_stars = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

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
