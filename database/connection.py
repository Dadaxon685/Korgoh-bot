import os
import asyncpg

async def create_db_pool():
    # Railway-dagi DATABASE_URL ni o'qiymiz
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Agar mahalliy kompyuterda bo'lsangiz va DATABASE_URL bo'lmasa, eskisini ishlatadi
    if not DATABASE_URL:
        DATABASE_URL = "postgres://postgres:parol@127.0.0.1:5432/korgoh_db"

    # asyncpg ba'zan 'postgres://' ni xush ko'rmaydi, 'postgresql://' qilish kerak
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    try:
        pool = await asyncpg.create_pool(dsn=DATABASE_URL)
        print("✅ Baza bilan aloqa o'rnatildi!")
        return pool
    except Exception as e:
        print(f"❌ BAZAGA ULANISHDA XATOLIK: {e}")
        return None
