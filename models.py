from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

# TABEL: Menyimpan konfigurasi tiap server Discord & Sistem Lisensi
class ServerConfig(Base):
    __tablename__ = 'server_configs'
    
    guild_id = Column(String, primary_key=True) # ID Server Discord
    clan_tag = Column(String, nullable=False)   # Tag Clan CoC yang di-bind
    setup_by = Column(String)                   # User ID Leader yang nge-setup
    tier = Column(String, default="free")       # 'free', 'standar', 'ai_pro'
    expired_at = Column(DateTime, nullable=True)# Tanggal kedaluwarsa lisensi
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ClanMember(Base):
    __tablename__ = 'members'
    
    tag = Column(String, primary_key=True)
    clan_tag = Column(String, nullable=False)   # Milik clan mana
    name = Column(String, nullable=False)
    role = Column(String)
    townhall_level = Column(Integer)
    donations = Column(Integer, default=0)
    donations_received = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

class WarHistory(Base):
    __tablename__ = 'war_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    clan_tag = Column(String, nullable=False)   # Milik clan mana
    opponent_name = Column(String)
    opponent_tag = Column(String)
    result = Column(String)
    stars = Column(Integer)
    destruction_percentage = Column(Integer)
    end_time = Column(DateTime, default=datetime.datetime.utcnow)
