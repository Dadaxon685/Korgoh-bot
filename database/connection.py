import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def create_db_pool():
    try:
        # Parametrlarni chop etamiz (parolni yashirin tutgan holda)
        print(f"🔄 Ulanishga urinish: {os.getenv('DB_USER')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
        
        pool = await asyncpg.create_pool(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            database=os.getenv("DB_NAME"),
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", 5432)),
            # Ulanish vaqtini biroz uzaytiramiz
            command_timeout=60
        )
        print("✅ PostgreSQL bazasiga ulanish muvaffaqiyatli!")
        return pool
    except Exception as e:
        print("\n❌ BAZAGA ULANISHDA XATOLIK:")
        print(f"Xabar: {e}")
        print("-" * 30)
        return None