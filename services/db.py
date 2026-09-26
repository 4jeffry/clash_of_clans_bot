import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, ServerConfig
from datetime import datetime

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

def check_standar_access(guild_id: str) -> tuple[bool, str]:
    """Mengecek apakah server memiliki akses minimal Tier Standar"""
    db = get_db()
    try:
        config = db.query(ServerConfig).filter(ServerConfig.guild_id == str(guild_id)).first()
        if not config:
            return False, "❌ Server ini belum di-setup! Gunakan `/setup` terlebih dahulu."
        
        now = datetime.now()
        tier = str(config.tier).lower() if config.tier else "free"
        
        # Free Tier Ditolak
        if tier == "free":
            return False, (
                "🔒 **Fitur Khusus Tier Standar**\n"
                "Command ini membutuhkan akses **Tier Standar** (Rp10.000/bulan).\n"
                "Hubungi Admin Ixiera (`ixiera.id`) untuk membuka semua fitur utility & auto alert!"
            )
            
        # Cek Expiry (Jika tier Pro atau Standar)
        if config.expired_at and config.expired_at < now:
            return False, "⚠️ **Masa Aktif Lisensi Habis**. Hubungi Admin Ixiera untuk memperpanjang!"
            
        return True, ""
    finally:
        db.close()
