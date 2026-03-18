import asyncio
from aiogram import Bot, Dispatcher
from database.connection import create_db_pool # O'zingizni ulanish funksiyangiz
from middlewares.db import DbSessionMiddleware
from handlers import start, employer, admin, candidate # Routerlaringiz
import logging
import os



async def main():
    # 1. Baza poolini yaratish
    pool = await create_db_pool()
    if not pool:
        print("❌ Baza ulanmadi, bot to'xtatildi!")
        return

    bot = Bot(token=os.getenv("BOT_TOKEN")) 
    dp = Dispatcher()

    # 2. MIDDLEWARE (Har doim routerlardan oldin bo'lishi shart)
    dp.update.middleware.register(DbSessionMiddleware(pool))

    # 3. ROUTERLAR TARTIBI (Muhim!)
    # Admin har doim birinchi - uning huquqlari va buyruqlari ustuvor
    dp.include_router(admin.router)
    
    # Ish beruvchi va Nomzod routerlari
    dp.include_router(employer.router)
    dp.include_router(candidate.router)
    
    # Start (yoki umumiy) router eng oxirida
    # Chunki u eng umumiy handlerlarni (masalan, Reply tugmalarini) tutadi
    dp.include_router(start.router)

    print("🚀 Korgoh_uz tizimi ishga tushdi...")
    await dp.start_polling(bot)
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi")
