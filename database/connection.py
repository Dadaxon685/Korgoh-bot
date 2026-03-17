import os
import asyncpg
import logging

# Loglarni sozlash (xatoliklarni aniq ko'rish uchun)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_db_pool():
    # 1. Railway bergan DATABASE_URL ni olish
    # Agar Variables qismida DATABASE_URL bo'lmasa, None qaytaradi
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # 2. Agar DATABASE_URL bo'lmasa, local bazaga ulanish
    if not DATABASE_URL:
        # O'zingizning kompyuteringizdagi ma'lumotlar
        DATABASE_URL = "postgresql://postgres:parol@127.0.0.1:5432/korgoh_db"
        logger.info("ℹ️ Local (127.0.0.1) bazaga ulanishga urinish...")
    else:
        logger.info("🌐 Railway bazasiga ulanishga urinish...")

    # 3. asyncpg talabi: 'postgres://' ni 'postgresql://' ga o'zgartirish
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    try:
        # 4. Pool yaratish
        # ssl='require' Railway-da tashqi ulanish uchun shart
        pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
            # Faqat uzoqdagi (Railway) baza bo'lsa SSL ishlatadi
            ssl='require' if "127.0.0.1" not in DATABASE_URL and "localhost" not in DATABASE_URL else None
        )
        
        # Ulanishni tekshirib ko'rish
        async with pool.acquire() as connection:
            await connection.execute('SELECT 1')
            
        print("✅ Baza bilan aloqa muvaffaqiyatli o'rnatildi!")
        return pool

    except Exception as e:
        print(f"❌ BAZAGA ULANISHDA XATOLIK: {e}")
        logger.error(f"⚠️ Batafsil xatolik: {str(e)}")
        
        # Agar xato 'Name or service not known' bo'lsa, bu DATABASE_URL noto'g'ri degani
        if "Name or service not known" in str(e):
            logger.error("‼️ DATABASE_URL formatini tekshiring! Host topilmadi.")
            
        return None
