import os
import asyncpg
import logging

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_db_pool():
    url = os.getenv("DATABASE_URL")
    if not url: return None

    # Railway ichki tarmog'i (.internal) SSL rejimini yoqtirmasligi mumkin
    is_internal = "railway.internal" in url

    try:
        pool = await asyncpg.create_pool(
            dsn=url,
            # Ichki tarmoq bo'lsa SSLni o'chiramiz, tashqi bo'lsa yoqamiz
            ssl=None if is_internal else 'require',
            connect_timeout=30
        )
        
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
            
        print("✅ Baza bilan aloqa o'rnatildi!")
        return pool
    except Exception as e:
        print(f"❌ XATOLIK: {e}")
        return None
