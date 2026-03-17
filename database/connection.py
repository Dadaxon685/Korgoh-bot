import os
import asyncpg
import logging

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os
import asyncpg

async def create_db_pool():
    try:
        pool = await asyncpg.create_pool(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            database=os.getenv("DB_NAME"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            ssl='require' # Tashqi ulanish uchun shart
        )
        print("✅ Baza ulandi!")
        return pool
    except Exception as e:
        print(f"❌ Xato: {e}")
