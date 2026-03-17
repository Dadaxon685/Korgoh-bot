import asyncio
from datetime import datetime
# from dbm import _Database
import os
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from keyboards.inlines import admin_panel_keyboard
from utils.report_gen import generate_employer_report
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

# --- MODERATSIYA: TASDIQLASH ---import os
# from aiogram import Router, F, types, Bot
from aiogram.types import CallbackQuery

router = Router()
async def notify_matching_workers(bot: Bot, db_pool, soha: str, sub_sector: str, ad_id: int):
    async with db_pool.acquire() as conn:
        # 1. Shu sohaga qiziqish bildirgan ishchilarni topamiz
        # 'category' ustunida ishchining sohasi saqlangan deb hisoblaymiz
        workers = await conn.fetch("""
            SELECT user_id FROM users 
            WHERE role = 'user' AND category = $1 AND notifications = TRUE
        """, soha)

    if not workers:
        return

    # 2. Xabar matni
    text = (
        f"🔔 <b>Yangi e'lon!</b>\n\n"
        f"Sizning sohangiz bo'yicha yangi e'lon chiqdi:\n"
        f"💼 <b>Yo'nalish:</b> {soha} -> {sub_sector}\n\n"
        f"Ko'rish uchun quyidagi tugmani bosing 👇"
    )

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="👁 Ko'rish", callback_data=f"view_ad_{ad_id}"))

    # 3. Har bir ishchiga xabar yuboramiz
    for worker in workers:
        try:
            await bot.send_message(
                chat_id=worker['user_id'],
                text=text,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
            # Telegram cheklovlariga tushib qolmaslik uchun kichik tanaffus (ixtiyoriy)
            await asyncio.sleep(0.05) 
        except Exception as e:
            print(f"Xabar yuborishda xato (User: {worker['user_id']}): {e}")

@router.callback_query(F.data.startswith("view_ad_"))
async def view_specific_ad(callback: types.CallbackQuery, db_pool):
    # 1. ID ni callback_data dan ajratib olamiz
    ad_id = int(callback.data.split("_")[2])
    
    async with db_pool.acquire() as conn:
        # 2. Bazadan e'lon ma'lumotlarini va ish beruvchi ma'lumotlarini olamiz
        ad = await conn.fetchrow("SELECT * FROM ads WHERE id = $1", ad_id)
    
    if not ad:
        return await callback.answer("❌ Kechirasiz, e'lon topilmadi yoki o'chirib tashlangan.", show_alert=True)

    # 3. Chiroyli ko'rinishda matn yig'amiz
    # E'lon berilgan vaqtni chiroyli ko'rsatish (ixtiyoriy)
    date_str = ad['created_at'].strftime("%d.%m.%Y")

    text = (
        f"📋 <b>ISH E'LONI №{ad_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏢 <b>Soha:</b> {ad['soha']}\n"
        f"💼 <b>Lavozim:</b> {ad['sub_sector']}\n"
        f"📍 <b>Hudud:</b> {ad.get('region', 'Ko''rsatilmagan')}\n"
        f"💰 <b>Maosh:</b> {ad.get('salary', 'Kelishuv asosida')}\n"
        f"🕒 <b>Ish vaqti:</b> {ad.get('work_time', 'Noma''lum')}\n"
        f"🛠 <b>Bandlik turi:</b> {ad.get('job_type', 'Noma''lum')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🗓 <i>E'lon berilgan sana: {date_str}</i>"
    )

    # 4. Ariza topshirish tugmasi
    kb = InlineKeyboardBuilder()
    # Bu tugma bosilganda anketani to'ldirish (siz yozgan JobSeeker holati) boshlanadi
    kb.row(types.InlineKeyboardButton(
        text="📝 Ariza topshirish", 
        callback_data=f"room_sub_{ad['sub_sector']}" 
    ))
    # E'tibor bering: callback_data ni sizning mavjud anketangizga (room_sub_...) mosladim
    
    kb.row(types.InlineKeyboardButton(text="❌ Yopish", callback_data="delete_msg"))

    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "delete_msg")
async def delete_msg_handler(callback: types.CallbackQuery):
    await callback.message.delete()
    
@router.callback_query(F.data.startswith("approve_"))
async def approve_ad(callback: types.CallbackQuery, bot: Bot, db_pool):
    user_id = int(callback.data.split("_")[1])
    
    async with db_pool.acquire() as conn:
        # 1. Tadbirkor balansini va e'lon ma'lumotlarini olish
        ad_data = await conn.fetchrow("""
            SELECT a.*, r.room_number, u.balance 
            FROM ads a
            LEFT JOIN rooms r ON a.owner_id = r.owner_id
            LEFT JOIN users u ON u.user_id = a.owner_id
            WHERE a.owner_id = $1 AND a.status = 'pending'
            ORDER BY a.id DESC LIMIT 1
        """, user_id)

        if not ad_data:
            return await callback.answer("❌ E'lon topilmadi!", show_alert=True)

        if ad_data['balance'] < 10:
            return await callback.answer("❌ Tadbirkor balansida ball yetarli emas!", show_alert=True)

        # Ma'lumotlarni o'zgaruvchilarga olish
        ad_id = ad_data['id']
        soha = ad_data['soha']
        yonalish = ad_data['sub_sector']
        region = ad_data.get('region', "Ko'rsatilmagan")
        job_type = ad_data.get('job_type', "Ko'rsatilmagan")
        salary = ad_data.get('salary', "Kelishiladi")
        work_time = ad_data.get('work_time', "To'liq kun")
        room_num = ad_data['room_number'] or "Mavjud emas"

        # Talablar ro'yxatini shakllantirish (Mapping)
        req_mapping = {
            "full_name": "Ism-familiya", "age": "Yoshi", "phone": "Tel. raqami",
            "photo": "Rasm (3x4)", "voice": "Ovozli xabar", "portfolio": "Portfolio",
            "experience": "Ish tajribasi", "address": "Manzil"
        }
        raw_reqs = ad_data['selected_reqs'].split(",") if ad_data['selected_reqs'] else []
        talablar_str = "\n".join([f"    ✅ {req_mapping.get(r.strip(), r.strip())}" for r in raw_reqs])

        # Heshteglarni tayyorlash
        def clean_tag(text): return "".join(filter(str.isalnum, text.replace(" ", "_")))
        hashtag_text = f"#{clean_tag(soha)} #{clean_tag(yonalish)} #{clean_tag(region)} #ish_bor"

        # --- KANAL UCHUN PROFESSIONAL DIZAYN ---
        channel_text = (
            f"🚀 <b>YANGI VAKANSIYA: {yonalish.upper()}</b>\n\n"
            f"🏢 <b>Soha:</b> {soha}\n"
            f"📍 <b>Hudud:</b> {region} ({job_type})\n"
            f"💰 <b>Maosh:</b> {salary}\n"
            f"⏰ <b>Ish vaqti:</b> {work_time}\n"
            f"🔢 <b>Xona raqami:</b> <code>{room_num}</code>\n\n"
            f"📋 <b>Nomzoddan talab qilinadi:</b>\n"
            f"{talablar_str}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔍 <b>Arizani qanday topshirish mumkin?</b>\n"
            f"1️⃣ Botga kiring: @korgoh_uz_bot\n"
            f"2️⃣ <b>Xona raqami</b> tugmasini bosib <code>{room_num}</code> raqamini yuboring\n\n"
            f"📢 @Korgoh_ish_kanali\n"
            f"<i>{hashtag_text}</i>"
        )

        channel_id = os.getenv("CHANNEL_ID")
        
        try:
            # Kanalga yuborish
            await bot.send_message(chat_id=channel_id, text=channel_text, parse_mode="HTML")
            
            # Balans yechish va statusni yangilash
            await conn.execute("UPDATE users SET balance = balance - 10 WHERE user_id = $1", user_id)
            await conn.execute("UPDATE ads SET status = 'approved' WHERE id = $1", ad_id)
            
            # Tadbirkorga xabar
            await bot.send_message(user_id, f"✅ Tabriklaymiz! <b>{yonalish}</b> bo'yicha e'loningiz kanalga chiqdi.", parse_mode="HTML")
            await notify_matching_workers(
                    bot=bot, 
                    db_pool=db_pool, 
                    soha=ad_data['soha'], 
                    sub_sector=ad_data['sub_sector'], 
                    ad_id=ad_id
                )
                        
            # Admin panelini yangilash
            await callback.message.edit_text(
                f"{callback.message.text}\n\n✅ <b>TASDIQLANDI</b>\n💰 10 ball yechildi.", 
                parse_mode="HTML"
            )
            await callback.answer("E'lon muvaffaqiyatli chop etildi!")

        except Exception as e:
            print(f"Kanalga yuborishda xato: {e}")
            await callback.answer("❌ Kanalga yuborishda xatolik yuz berdi!", show_alert=True)
@router.callback_query(F.data.startswith("rej_cand_"))
async def reject_candidate_full(callback: types.CallbackQuery, bot: Bot, db_pool):
    # 1. IDlarni ajratib olamiz
    # callback_data: "rej_cand_{candidate_id}"
    try:
        data_parts = callback.data.split("_")
        candidate_id = int(data_parts[2])
        owner_id = callback.from_user.id  # Tadbirkor ID
    except (IndexError, ValueError):
        return await callback.answer("Ma'lumot olishda xato!")

    # 2. BAZADAN O'CHIRISH (SQL)
    # Nomzod yuborgan e'lonni 'ads' yoki 'applications' jadvalidan o'chiramiz
    async with db_pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM ads 
            WHERE owner_id = $1 AND status = 'pending' 
            AND id = (SELECT id FROM ads WHERE owner_id = $1 ORDER BY id DESC LIMIT 1)
        """, owner_id)
        # Eslatma: Agar sizda alohida arizalar jadvali bo'lsa, o'shandan o'chiring

    # 3. TADBIRKOR EKRANINI TOZALASH
    # a) Asosiy xabarni (Rasm + Matn) o'chirish
    try:
        main_msg_id = callback.message.message_id
        await callback.message.delete()
    except Exception as e:
        print(f"Asosiy xabarni o'chirishda xato: {e}")

    # b) Ovozli xabarni o'chirish
    # Sizning kodingizda ovozli xabar asosiy xabardan keyin yuborilgan (ID + 1 bo'ladi)
    try:
        await bot.delete_message(chat_id=owner_id, message_id=main_msg_id + 1)
    except Exception:
        # Agar ovozli xabar bo'lmasa yoki allaqachon o'chgan bo'lsa xato bermaydi
        pass

    # 4. NOMZODGA JAVOB YUBORISH
    try:
        await bot.send_message(
            chat_id=candidate_id,
            text="❌ **Arizangiz ko'rib chiqildi va rad etildi.**\n"
                 "Ma'lumotlaringiz bazadan o'chirildi."
        )
    except Exception:
        pass

    # 5. ADMINGA TASDIQ
    await callback.answer("Ariza va barcha fayllar o'chirildi.", show_alert=True)
# --- ADMIN STATISTIKASI ---
@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: types.CallbackQuery, db_pool):
    async with db_pool.acquire() as conn:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        rooms_count = await conn.fetchval("SELECT COUNT(*) FROM rooms")
        # Foyda (faqat to'lov tizimi ishlagan bo'lsa)
        # profit = await conn.fetchval("SELECT SUM(amount) FROM payments WHERE status = 'completed'") or 0

    stats_text = (
        "📊 **BOT STATISTIKASI**\n\n"
        f"👤 Jami foydalanuvchilar: {users_count} ta\n"
        f"🏢 Sotilgan xonalar: {rooms_count} ta\n"
        # f"💰 Umumiy tushum: {profit:,} so'm"
    )
    
    await callback.message.answer(stats_text)
    await callback.answer()

# --- ADMIN PANELIGA KIRISH (KOMANDA ORQALI) ---
@router.message(Command("admin"))
async def admin_start(message: types.Message):
    if str(message.from_user.id) == os.getenv("ADMIN_ID"):
        await message.answer("Xush kelibsiz, Admin! 👑", reply_markup=admin_panel_keyboard())
    else:
        await message.answer("Siz admin emassiz! 🚫")



from aiogram.fsm.state import State, StatesGroup
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext

class AdminStates(StatesGroup):
    waiting_broadcast_msg = State()

@router.callback_query(F.data == "broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 <b>Hammaga yuboriladigan xabarni kiriting:</b>\n\n<i>(Rasm, video yoki matn bo'lishi mumkin)</i>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_broadcast_msg)

@router.message(AdminStates.waiting_broadcast_msg)
async def send_broadcast(message: types.Message, state: FSMContext, db_pool, bot: Bot):
    async with db_pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM users")

    count = 0
    await message.answer("⏳ Xabar yuborish boshlandi...")
    
    for user in users:
        try:
            await message.copy_to(chat_id=user['user_id'])
            count += 1
        except Exception:
            continue # Bloklagan bo'lsa o'tib ketadi
            
    await message.answer(f"✅ Xabar <b>{count}</b> ta foydalanuvchiga muvaffaqiyatli yetkazildi!", parse_mode="HTML")
    await state.clear()


class BlockState(StatesGroup):
    waiting_user_id = State()

@router.callback_query(F.data == "block_user")
async def block_user_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🚫 <b>Bloklamoqchi bo'lgan foydalanuvchi ID sini yuboring:</b>", parse_mode="HTML")
    await state.set_state(BlockState.waiting_user_id)

@router.message(BlockState.waiting_user_id)
async def process_block(message: types.Message, state: FSMContext, db_pool):
    if not message.text.isdigit():
        return await message.answer("⚠️ Iltimos, faqat raqamlardan iborat ID yuboring!")

    target_id = int(message.text)
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET status = 'blocked' WHERE user_id = $1", target_id)
    
    await message.answer(f"✅ Foydalanuvchi {target_id} bloklandi!")
    await state.clear()


from aiogram.types import BufferedInputFile

@router.callback_query(F.data == "admin_report_excel")
async def send_report(callback: types.CallbackQuery, db_pool):
    await callback.answer("⏳ Hisobot tayyorlanmoqda...")
    
    # Hisobotni generatsiya qilish
    excel_file = await generate_employer_report(db_pool)
    
    # Fayl nomi
    today = datetime.now().strftime("%d-%m-%Y")
    filename = f"Tadbirkorlar_Hisobot_{today}.xlsx"
    
    # Faylni yuborish
    document = BufferedInputFile(excel_file.read(), filename=filename)
    
    await callback.message.answer_document(
        document=document,
        caption=f"📊 <b>Tadbirkorlar bo'yicha umumiy hisobot</b>\n📅 Sana: {today}\n\n"
                f"<i>Excel faylda faoliyat, premium status va e'lonlar soni jamlangan.</i>",
        parse_mode="HTML"
    )