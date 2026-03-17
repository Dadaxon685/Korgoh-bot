
import os
import asyncpg

import os
import asyncpg
import logging

async def create_db_pool():
    # Railway Variables bo'limidan bittama-bitta o'qiymiz
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_name = os.getenv("DB_NAME")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")

    # Agar birortasi topilmasa, logda ko'ramiz
    if not all([db_user, db_pass, db_name, db_host, db_port]):
        logging.error(f"❌ O'zgaruvchilar yetishmayapti: USER={db_user}, HOST={db_host}, PORT={db_port}")
        return None

    try:
        logging.info(f"🌐 Ulanish urinishi: {db_host}:{db_port}")
        
        pool = await asyncpg.create_pool(
            user=db_user,
            password=db_pass,
            database=db_name,
            host=db_host,
            port=int(db_port), # Port raqam bo'lishi shart
            ssl='require',     # Tashqi proxy uchun shart!
            command_timeout=60
        )
        
        # Aloqani tekshirish
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
            
        print("✅ TABRIKLAYMAN! Baza muvaffaqiyatli ulandi!")
        return pool

    except Exception as e:
        print(f"❌ BAZAGA ULANISHDA XATO: {e}")
        return None
