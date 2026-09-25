import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

logger = logging.getLogger('bot.db')

# Ambil URL dari environment, default ke SQLite untuk tes lokal di HP lu
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///clanbot.db")

# Fix kompatibilitas URL PostgreSQL di Railway
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("Database engine berhasil dibuat.")
except Exception as e:
    logger.error(f"Gagal membuat database engine: {e}")

def init_db():
    """Jalankan fungsi ini saat bot pertama kali nyala untuk membuat tabel"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tabel database berhasil diinisialisasi.")
    except Exception as e:
        logger.error(f"Gagal inisialisasi tabel: {e}")

def get_db():
    """Generator untuk mendapatkan sesi database"""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.close()
