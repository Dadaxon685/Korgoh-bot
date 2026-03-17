import os
import asyncpg
import logging

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_db_pool():
    # Railway-dagi Variables-dan o'qiymiz
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_name = os.getenv("DB_NAME")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")

    # Ma'lumotlar borligini tekshirish
    if not all([db_user, db_pass, db_name, db_host, db_port]):
        logger.error(f"❌ O'zgaruvchilar topilmadi! HOST: {db_host}, PORT: {db_port}")
        return None

    try:
        logger.info(f"🌐 Baza manziliga ulanish urinishi: {db_host}:{db_port}")
        
        pool = await asyncpg.create_pool(
            user=db_user,
            password=db_pass,
            database=db_name,
            host=db_host,
            port=int(db_port), # Port raqam (36558) bo'lishi shart
            ssl='require',     # Tashqi proxy uchun shart!
            command_timeout=60
        )
        
        # Aloqani tekshirish
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
            
        print("✅ TABRIKLAYMAN! Baza muvaffaqiyatli ulandi!")
        return pool

    except Exception as e:
        logger.error(f"❌ BAZAGA ULANISHDA XATO: {str(e)}")
        return None
