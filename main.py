import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from database.connection import create_db_pool  # Sizning funksiyangiz
# Agar DbSessionMiddleware ishlatsangiz, uni pastda ro'yxatdan o'tkazamiz
from middlewares.db import DbSessionMiddleware 
from handlers import start, employer, admin, candidate

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)

async def main():
    # 1. Ma'lumotlar bazasi poolini yaratish
    pool = await create_db_pool()
    
    if not pool:
        logging.error("❌ Baza ulanmadi, bot to'xtatildi!")
        return

    # Bot obyektini yaratish (Tokenni Environment orqali olish)
    token = os.getenv("BOT_TOKEN")
    if not token:
        logging.error("❌ BOT_TOKEN topilmadi!")
        return
        
    bot = Bot(token=token)
    dp = Dispatcher()

    # --- MIDDLEWARES ---
    # Agar middleware orqali bazani uzatmoqchi bo'lsangiz:
    # dp.update.outer_middleware(DbSessionMiddleware(pool))

    # --- ROUTERLAR ---
    # Routerlarni tartib bilan ulash
    dp.include_router(admin.router)      # 👑 Admin
    dp.include_router(employer.router)   # 💼 Tadbirkor
    dp.include_router(candidate.router)  # 👤 Nomzod
    dp.include_router(start.router)      # 🚀 Start (Eng oxirida bo'lgani ma'qul)

    print("🚀 Korgoh_uz tizimi ishga tushdi...")

    try:
        # 2. ENG MUHIM QISMI: pool'ni workflow_data sifatida uzatish
        # Shunda handlerlarda 'db_pool' (yoki 'pool') argumentini ishlatish mumkin bo'ladi
        await dp.start_polling(bot, db_pool=pool) 
    finally:
        await pool.close() # Bot to'xtaganda bazani yopish
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi")
