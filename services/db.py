import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

logger = logging.getLogger('bot.db')

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///clanbot.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    engine_args = {
        "pool_pre_ping": True,  # Cek koneksi aktif/enggak sebelum query biar kagak dropped oleh Supabase
        "pool_recycle": 300,    # Recycle koneksi tiap 5 menit
    }
    
    # Konfigurasi khusus PostgreSQL/Psycopg3 biar ramah sama Supabase PgBouncer (Transaction Pooler)
    if "postgresql" in DATABASE_URL:
        engine_args["connect_args"] = {
            "prepare_threshold": None  # Matikan prepared statement pemicu error _pg3_0
        }

    engine = create_engine(DATABASE_URL, **engine_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("Database engine berhasil dibuat (Compatible dengan Supabase Pooler).")
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
