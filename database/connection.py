import os
import asyncpg

async def create_db_pool():
    # Railway-dagi o'zgaruvchini o'qiymiz
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Agar mahalliy kompyuterda ishlayotgan bo'lsangiz:
    if not DATABASE_URL:
        DATABASE_URL = "postgres://postgres:parol@127.0.0.1:5432/korgoh_db"

    # asyncpg uchun 'postgres://' ni 'postgresql://' ga almashtirish shart
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    try:
        # SSL rejimini Railway uchun 'require' qilish tavsiya etiladi
        pool = await asyncpg.create_pool(dsn=DATABASE_URL, ssl='require')
        print("✅ Baza bilan aloqa o'rnatildi!")
        return pool
    except Exception as e:
        print(f"❌ BAZAGA ULANISHDA XATOLIK: {e}")
        return None
