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

    bot = Bot(token=os.getenv("BOT_TOKEN")) # .env dan oladi
    dp = Dispatcher()

    # 2. MIDDLEWARENI RO'YXATDAN O'TKAZISH (Routerlardan oldin ulanadi)
    dp.update.middleware.register(DbSessionMiddleware(pool))

    dp.include_router(start.router)
    dp.include_router(employer.router)
    dp.include_router(admin.router)
    dp.include_router(candidate.router)

    print("🚀 Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi")