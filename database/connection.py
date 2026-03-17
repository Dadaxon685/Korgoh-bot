import os
import asyncpg
import logging

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_db_pool():
    # Railway'dan URLni olamiz va atrofidagi bo'shliqlarni olib tashlaymiz
    url = os.getenv("DATABASE_URL")
    
    if not url:
        logger.error("❌ DATABASE_URL topilmadi! Railway Variables bo'limini tekshiring.")
        return None

    # Bo'sh joylar yoki ortiqcha belgilarni tozalash (MUHIM!)
    url = url.strip()

    # asyncpg uchun formatni to'g'rilash
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    try:
        logger.info("🌐 Ma'lumotlar bazasiga ulanishga urinish...")
        
        pool = await asyncpg.create_pool(
            dsn=url,
            ssl='require', # Railway uchun shart
            min_size=1,
            max_size=10
        )
        
        # Haqiqiy ulanishni tekshirish
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
            
        print("✅ Baza bilan aloqa muvaffaqiyatli o'rnatildi!")
        return pool

    except Exception as e:
        logger.error(f"❌ BAZAGA ULANISHDA XATOLIK: {str(e)}")
        return None
