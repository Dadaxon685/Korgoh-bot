import re
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

def clean_text(text):
    """Matnni harf xatolariga chidamli qilish uchun tozalash"""
    if not text: 
        return ""
    text = text.lower()
    # O'zbekcha harflardagi belgilarni tozalash (o', g' kabi)
    text = text.replace("'", "").replace("`", "").replace("ʻ", "").replace("’", "")
    text = text.replace("g‘", "g").replace("o‘", "o").replace("g'", "g").replace("o'", "o")
    # Bo'shliqlarni olib tashlash (buxgalter yordamchisi -> buxgalteryordamchisi)
    return re.sub(r'\s+', '', text).strip()

async def send_matching_notifications(bot: Bot, db_pool, ad_id, category, title, salary):
    # E'lon sohasini va sarlavhasini tozalaymiz
    clean_ad_cat = clean_text(category)
    clean_ad_title = clean_text(title)

    async with db_pool.acquire() as conn:
        # Avval bildirishnomasi yoqilgan hamma nomzodlarni olamiz
        candidates = await conn.fetch("""
            SELECT user_id, category FROM users 
            WHERE role = 'candidate' AND notifications = TRUE
        """)

    if not candidates:
        return

    text = (
        "🔔 **Siz uchun mos yangi ish!**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **Soha:** {category}\n"
        f"💼 **Lavozim:** {title}\n"
        f"💰 **Maosh:** {salary}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👉 Batafsil ko'rish uchun pastdagi tugmani bosing."
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="👁 Ko'rish", callback_data=f"view_ad_{ad_id}")

    count = 0
    for cand in candidates:
        # Nomzodning sohasini tozalaymiz
        clean_user_cat = clean_text(cand['category'])

        # --- FILTRLASH MANTIQI ---
        # Agar nomzod sohasida tadbirkor yozgan so'z bo'lsa yoki aksincha
        if clean_user_cat in clean_ad_cat or clean_user_cat in clean_ad_title or clean_ad_title in clean_user_cat:
            try:
                await bot.send_message(cand['user_id'], text, reply_markup=kb.as_markup(), parse_mode="Markdown")
                count += 1
            except Exception:
                continue
    
    print(f"DEBUG: {count} ta nomzodga o'xshashlik bo'yicha xabar yuborildi.")