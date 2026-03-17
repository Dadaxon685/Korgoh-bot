import os
import asyncpg
import logging

async def create_db_pool():
    # 1. Railway bergan DATABASE_URL ni olishga urinamiz
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # 2. Agar DATABASE_URL topilmasa (masalan, o'z kompyuteringizda), eski usulda ulanamiz
    if not DATABASE_URL:
        # O'zingizning local ma'lumotlaringizni yozing
        DATABASE_URL = "postgres://postgres:parol@127.0.0.1:5432/korgoh_db"
        logging.info("ℹ️ Local bazaga ulanishga urinish...")
    else:
        logging.info("🌐 Railway bazasiga ulanishga urinish...")

    # 3. asyncpg uchun 'postgres://' ni 'postgresql://' ga o'zgartirish (Railway talabi)
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    try:
        # Railway-da tashqi ulanish uchun ssl='require' shart bo'lishi mumkin
        # Localda ishlamasa, ssl=None qilib ko'ring
        pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            ssl='require' if "railway.app" in DATABASE_URL or "railway" in DATABASE_URL else None
        )
        print("✅ Baza bilan aloqa o'rnatildi!")
        return pool
    except Exception as e:
        print(f"❌ BAZAGA ULANISHDA XATOLIK: {e}")
        # Xatoni aniqroq ko'rish uchun:
        logging.error(f"Xato tafsiloti: {str(e)}")
        return None
