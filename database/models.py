async def add_user_to_db(pool, user_id, full_name):
    async with pool.acquire() as connection:
        # Foydalanuvchi bor bo'lsa yangilaydi, bo'lmasa qo'shadi
        await connection.execute("""
            INSERT INTO users (user_id, full_name)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, full_name)