from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class ClanMember(Base):
    __tablename__ = 'members'
    
    tag = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    role = Column(String)
    townhall_level = Column(Integer)
    donations = Column(Integer, default=0)
    donations_received = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

class WarHistory(Base):
    __tablename__ = 'war_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    opponent_name = Column(String)
    opponent_tag = Column(String)
    result = Column(String) # win, lose, tie
    stars = Column(Integer)
    destruction_percentage = Column(Integer)
    end_time = Column(DateTime, default=datetime.datetime.utcnow)
