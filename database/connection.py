import os
import asyncpg
import logging

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_db_pool():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("❌ DATABASE_URL topilmadi!")
        return None

    # asyncpg uchun formatni to'g'rilash
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    try:
        # Xatoni keltirib chiqargan 'connect_timeout' olib tashlandi
        # O'rniga 'command_timeout' ishlatish mumkin yoki shunchaki o'chirib qo'ying
        pool = await asyncpg.create_pool(
            dsn=url,
            ssl='require' if "railway.internal" not in url else None,
            command_timeout=60  # connect_timeout o'rniga shu ishlatiladi
        )
        
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
            
        print("✅ Baza bilan aloqa muvaffaqiyatli o'rnatildi!")
        return pool
    except Exception as e:
        print(f"❌ XATOLIK: {e}")
        return None
