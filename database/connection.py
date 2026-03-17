import os
import asyncpg
import logging

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_db_pool():
    # Railway Variables bo'limidan ma'lumotlarni o'qiymiz
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_name = os.getenv("DB_NAME")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")

    # O'zgaruvchilar borligini tekshirish
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
            port=int(db_port),
            ssl='require',
            command_timeout=60
        )
        
        # Jadvallarni avtomatik yaratish bloki
        async with pool.acquire() as conn:
            # 1. Extension (Qidiruv uchun)
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

            # 2. Users jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    full_name VARCHAR(255),
                    role TEXT DEFAULT 'user',
                    balance INTEGER DEFAULT 0,
                    notifications BOOLEAN DEFAULT TRUE,
                    category TEXT,
                    age INTEGER,
                    experience TEXT,
                    photo_id TEXT,
                    voice_id TEXT,
                    phone TEXT,
                    employer_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 3. Rooms jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id SERIAL PRIMARY KEY,
                    room_number VARCHAR(20) UNIQUE,
                    room_type VARCHAR(20),
                    price DECIMAL(12, 2),
                    owner_id BIGINT REFERENCES users(user_id),
                    is_sold BOOLEAN DEFAULT FALSE
                );
            """)

            # 4. Favorites jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id SERIAL PRIMARY KEY,
                    employer_id BIGINT,
                    candidate_id BIGINT,
                    candidate_data TEXT,
                    info JSONB,
                    owner_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 5. Ads (E'lonlar) jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ads (
                    id SERIAL PRIMARY KEY,
                    owner_id BIGINT NOT NULL,
                    soha TEXT NOT NULL,
                    sub_sector TEXT NOT NULL,
                    selected_reqs TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    view_count INTEGER DEFAULT 0,
                    region TEXT,
                    job_type TEXT,
                    salary TEXT,
                    work_time TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 6. Resumes jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    user_id BIGINT PRIMARY KEY,
                    full_name TEXT,
                    phone TEXT,
                    info_json JSONB,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

        print("✅ TABRIKLAYMAN! Baza ulandi va barcha jadvallar muvaffaqiyatli tekshirildi!")
        return pool

    except Exception as e:
        logger.error(f"❌ BAZAGA ULANISHDA YOKI JADVALLARDA XATO: {str(e)}")
        return None
