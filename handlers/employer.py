import os
import random
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from states.states import AdCreation
from aiogram.exceptions import TelegramBadRequest
from states.states import ContactState
from keyboards.inlines import (
    admin_panel_keyboard,
    candidate_panel_keyboard,
    get_fav_keyboard,
    room_types_keyboard, 
    payment_type_keyboard, 
    employer_panel_keyboard,
    sectors_keyboard,        # Yangi: Sohvalar uchun
    requirements_keyboard ,
    regions_keyboard
)

router = Router()




# handlers/employer.py (yoki main.py) ichiga qo'shing
@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


# --- YORDAMCHI FUNKSIYALAR ---
import random

def get_number_by_plan(plan):
    plan = plan.lower()
    
    if plan == "gold":
        # Gold raqamlar: Faqat 10 ta maxsus to'rt xonali raqam (masalan, 0000, 1111, ..., 9999)
        # Yoki o'zingiz xohlagan 10 ta aniq raqamni ro'yxatga kiritishingiz mumkin
        gold_list = [f"{i}"*4 for i in range(10)] 
        return random.choice(gold_list)
    
    elif plan == "silver":
        a = random.randint(0, 9)
        b = random.randint(0, 9)
        # b a dan farqli bo'lishi uchun (xxyy va hokazo chiroyli chiqishi uchun)
        while a == b:
            b = random.randint(0, 9)
            
        patterns = [
            f"{a}{a}{b}{b}",    # xxyy
            f"777{a}",         # 777x
            f"{a}777",         # x777
            f"{a}{b}{b}{b}",    # xyyy
            f"{b}{b}{b}{a}"     # yyyx
        ]
        return random.choice(patterns)
    
    elif plan == "titan":
        # Titan: Mutlaqo tasodifiy 4 xonali raqam
        return f"{random.randint(0, 9999):04d}"
    
    else:
        # Standart holat (agar plan xato kiritilsa)
        return f"{random.randint(0, 9999):04d}"

# Tekshirish uchun:
# print(f"Gold: {get_number_by_plan('gold')}")
# print(f"Silver: {get_number_by_plan('silver')}")
# print(f"Titan: {get_number_by_plan('titan')}")
# --- TO'LOV TIZIMI ---

@router.callback_query(F.data.startswith("buy_room_"))
async def select_room_plan(callback: types.CallbackQuery, state: FSMContext):
    # buy_room_standard -> standard
    plan = callback.data.split("_")[2]
    
    # State-ga tanlangan tarifni saqlaymiz
    await state.update_data(selected_plan=plan)
    
    # Endi foydalanuvchini to'lov tasdiqlash tugmasiga (pay_click_1) yuboramiz
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="✅ Davom etish", callback_data="pay_click_1"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="buy_room_menu"))
    
    await callback.message.edit_text(
        f"Siz <b>{plan.upper()}</b> tarifini tanladingiz.\n"
        f"{'Bu tarif mutlaqo bepul!' if plan == 'standard' else 'Davom etish uchun to\'lovni amalga oshiring.'}",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "pay_click_1")
async def process_click_pay(callback: types.CallbackQuery, bot: Bot, state: FSMContext, db_pool):
    data = await state.get_data()
    plan = data.get("selected_plan", "standard").lower()
    
    # 1. AGAR STANDARD BO'LSA - BEPUL RAQAM BERISH
    if plan == "standard":
        user_id = callback.from_user.id
        
        async with db_pool.acquire() as conn:
            # Takrorlanmas raqam generatsiya qilish
            while True:
                num = get_number_by_plan("standard")
                exists = await conn.fetchval("SELECT 1 FROM rooms WHERE room_number = $1", num)
                if not exists: break
            
            # Xonani bazaga tekin (is_sold=TRUE) deb yozamiz
            await conn.execute(
                "INSERT INTO rooms (room_number, room_type, owner_id, is_sold) VALUES ($1, $2, $3, TRUE)",
                num, "standard", user_id
            )
            
            # Foydalanuvchi rolini ham yangilab qo'yamiz (agar kerak bo'lsa)
            await conn.execute("UPDATE users SET role = 'employer' WHERE user_id = $1", user_id)

        await callback.message.edit_text(
            f"🎁 **Tabriklaymiz!**\n\n"
            f"Sizga Standard tarif bo'yicha bepul xona berildi!\n"
            f"Xona raqamingiz: 🔥 `{num}` 🔥\n\n"
            f"Endi /panel orqali ishni boshlashingiz mumkin!",
            parse_mode="Markdown"
        )
        await state.clear()
        return # To'lov qismiga o'tmaydi

    # 2. AGAR PULLIK TARIFLAR (SILVER, GOLD) BO'LSA - TO'LOVGA YUBORISH
    prices_map = {"silver": 150000, "gold": 500000}
    amount = prices_map.get(plan)

    if not amount:
        return await callback.answer("Noma'lum tarif!")

    await callback.message.delete()
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{plan.upper()} Xona",
        description=f"Korgoh: {plan} darajali pullik raqam",
        payload=f"pay_room_{plan}", # Payloadni aniq qildik
        provider_token=os.getenv("CLICK_TOKEN"),
        currency="UZS",
        prices=[LabeledPrice(label=f"{plan.capitalize()} xona", amount=amount * 100)]
    )

@router.pre_checkout_query()
async def checkout_handler(pre_checkout: PreCheckoutQuery):
    await pre_checkout.answer(ok=True)

from keyboards.inlines import employer_panel_keyboard # Importni tekshir!

@router.message(F.successful_payment)
async def unified_payment_handler(message: types.Message, db_pool, bot: Bot):
    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id
    
    # 1. To'lov kelganini tasdiqlash uchun log
    print(f"To'lov qabul qilindi! User: {user_id}, Payload: {payload}")

    try:
        # --- 1-HOLAT: BALL SOTIB OLISH ---
        if "refill_ball" in payload:
            ball_added = int(payload.split("_")[-1]) # Oxirgi raqamni olish

            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET balance = COALESCE(balance, 0) + $1 WHERE user_id = $2", 
                    ball_added, user_id
                )
                room = await conn.fetchrow("SELECT room_number FROM rooms WHERE owner_id = $1", user_id)
            
            await message.answer(f"✅ Balans to'ldirildi: +{ball_added} ball")
            if room:
                return await message.answer("Panelga qaytish:", reply_markup=employer_panel_keyboard(room['room_number']))

        # --- 2-HOLAT: XONA SOTIB OLISH ---
        elif "buy_room" in payload or "pay_" in payload:
            # Payloadni to'g'ri kesib olish (masalan: pay_gold bo'lsa 'gold')
            plan = payload.split("_")[-1] 
            
            async with db_pool.acquire() as conn:
                # Yangi raqam generatsiyasi (Sening funksiyang)
                num = get_number_by_plan(plan) 
                
                # Rolni yangilash
                await conn.execute("UPDATE users SET role = 'employer' WHERE user_id = $1", user_id)
                
                # Xonani yozish
                await conn.execute("DELETE FROM rooms WHERE owner_id = $1", user_id)
                await conn.execute(
                    "INSERT INTO rooms (room_number, room_type, owner_id, is_sold) VALUES ($1, $2, $3, TRUE)",
                    num, plan, user_id
                )

            await message.answer(
                f"🎊 Tabriklaymiz! To'lov muvaffaqiyatli!\n🏢 Sizning xonangiz: <b>{num}</b>",
                reply_markup=employer_panel_keyboard(num),
                parse_mode="HTML"
            )
            
            # Adminga hisobot
            return await bot.send_message(os.getenv("ADMIN_ID"), f"💰 Xona sotildi: {num}")

    except Exception as e:
        print(f"XATOLIK YUZ BERDI: {e}")
        await message.answer("⚠️ To'lov qabul qilindi, lekin ma'lumotlarni yangilashda xato chiqdi. Admin bilan bog'laning.")@router.message(Command("panel"))
async def show_panel(message: types.Message, db_pool):
    user_id = message.from_user.id
    
    async with db_pool.acquire() as conn:
        # ORDER BY rooms.id DESC qo'shildi - bu eng oxirgi sotib olingan xonani olib keladi
        user = await conn.fetchrow("""
            SELECT users.role, rooms.room_number 
            FROM users 
            LEFT JOIN rooms ON users.user_id = rooms.owner_id 
            WHERE users.user_id = $1 
            ORDER BY rooms.id DESC LIMIT 1
        """, user_id)

    if not user:
        await message.answer("Avval ro'yxatdan o'ting! /start")
        return

    if user['role'] == 'employer':
        room_num = user['room_number'] or "Mavjud emas"
        # MarkdownV2 ishlatilsa xona raqamini ` ` ichiga olish chiroyli chiqadi
        await message.answer(
            f"🏢 **Tadbirkor paneli**\nXona raqamingiz: `{room_num}`", 
            reply_markup=employer_panel_keyboard(room_num),
            parse_mode="Markdown"
        )
    
    elif user['role'] == 'candidate':
        await message.answer("🔍 **Nomzod paneli**", reply_markup=candidate_panel_keyboard())

    # Admin tekshiruvi
    if str(user_id) == os.getenv("ADMIN_ID"):
        await message.answer("👑 **Admin paneli**", reply_markup=admin_panel_keyboard())


from aiogram.filters import Command

@router.message(Command("panel"))
async def show_employer_panel(message: types.Message, db_pool):
    user_id = message.from_user.id
    
    async with db_pool.acquire() as conn:
        # Foydalanuvchining xona raqamini bazadan qidiramiz
        room = await conn.fetchrow("SELECT room_number FROM rooms WHERE owner_id = $1", user_id)
        
    if room:
        room_num = room['room_number']
        text = (
            f"🏢 Sizning boshqaruv panelingiz\n"
            f"Xona raqami: `{room_num}`\n\n"
            f"Quyidagi amallardan birini tanlang:"
        )
        await message.answer(text, reply_markup=employer_panel_keyboard(room_num), parse_mode="Markdown")
    else:
        # Agar xonasi bo'lmasa
        await message.answer("❌ Kechirasiz, sizda hali faol ofis (xona) mavjud emas.")
        # 1. Sohani tanlash (New Ad bosilganda)
# 1. Boshlanishi: Sohani tanlash
@router.callback_query(F.data == "new_ad")
async def start_ad(callback: types.CallbackQuery, state: FSMContext, db_pool):
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        balance = await conn.fetchval("SELECT balance FROM users WHERE user_id = $1", user_id)
    
    if (balance or 0) < 10:
        return await callback.answer("⚠️ Balans yetarli emas (10 ball kerak)!", show_alert=True)

    await state.set_state(AdCreation.sector)
    await callback.message.edit_text("📝 <b>Sohani tanlang:</b>", reply_markup=sectors_keyboard(), parse_mode="HTML")

# 2. Soha tanlanganda -> Yo'nalishni yozish
@router.callback_query(AdCreation.sector, F.data.startswith("setsector_"))
async def process_sector(callback: types.CallbackQuery, state: FSMContext):
    sector_name = callback.data.split("_")[1]
    await state.update_data(chosen_sector=sector_name)
    await state.set_state(AdCreation.custom_service) 
    await callback.message.edit_text(f"✅ Soha: <b>{sector_name}</b>\n📝 Yo'nalishni yozing (masalan: Backend Developer):", parse_mode="HTML")

# 3. Yo'nalish yozilganda -> Talablar (Galochkalar)
@router.message(AdCreation.custom_service)
async def get_custom_service(message: types.Message, state: FSMContext):
    await state.update_data(chosen_sub=message.text, selected_reqs=[]) 
    await state.set_state(AdCreation.requirements)
    await message.answer("📋 Nomzoddan nimalarni talab qilasiz?", reply_markup=requirements_keyboard([]), parse_mode="HTML")

# 4. Galochkalar mantiqi
@router.callback_query(AdCreation.requirements, F.data.startswith("req_"))
async def toggle_req(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    reqs = data.get("selected_reqs", [])
    current = callback.data.replace("req_", "")
    if current in reqs: reqs.remove(current)
    else: reqs.append(current)
    await state.update_data(selected_reqs=reqs)
    await callback.message.edit_reply_markup(reply_markup=requirements_keyboard(reqs))
    await callback.answer()

# 5. Talablar tugagach -> VILOYAT (12 ta tugma)
@router.callback_query(AdCreation.requirements, F.data == "finish_ad")
async def ask_region(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdCreation.region)
    await callback.message.edit_text("📍 <b>Ish qaysi hududda? (Viloyatni tanlang):</b>", reply_markup=regions_keyboard(), parse_mode="HTML")

# 6. Viloyat tanlangach -> ISH TURI (Online/Offline)
@router.callback_query(AdCreation.region, F.data.startswith("reg_"))
async def process_region(callback: types.CallbackQuery, state: FSMContext):
    region = callback.data.split("_")[1]
    await state.update_data(chosen_region=region)
    await state.set_state(AdCreation.job_type)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🏠 Online", callback_data="type_Online")
    kb.button(text="🏢 Offline", callback_data="type_Offline")
    await callback.message.edit_text(f"📍 Hudud: {region}\n💻 <b>Ish turini tanlang:</b>", reply_markup=kb.as_markup(), parse_mode="HTML")

# 7. Ish turi tanlangach -> MAOSH
@router.callback_query(AdCreation.job_type, F.data.startswith("type_"))
async def process_job_type(callback: types.CallbackQuery, state: FSMContext):
    j_type = callback.data.split("_")[1]
    await state.update_data(chosen_job_type=j_type)
    await state.set_state(AdCreation.salary)
    await callback.message.edit_text("💰 <b>Ish haqqini yozing:</b>\n(Masalan: 500$ yoki Kelishiladi)", parse_mode="HTML")

# 8. Maosh yozilgach -> ISH VAQTI
@router.message(AdCreation.salary)
async def process_salary(message: types.Message, state: FSMContext):
    await state.update_data(chosen_salary=message.text)
    await state.set_state(AdCreation.work_time)
    await message.answer("⏰ <b>Ish vaqtini yozing:</b>\n(Masalan: 09:00 - 18:00)", parse_mode="HTML")

# 9. FINAL: Adminga Kanal Stilida yuborish
# 9. ISH VAQTI YAZILGANDA -> PREVIEW (Tadbirkorga ko'rsatish)
@router.message(AdCreation.work_time)
async def preview_ad(message: types.Message, state: FSMContext):
    await state.update_data(chosen_work_time=message.text)
    data = await state.get_data()
    
    # Ma'lumotlarni yig'ish
    sector = data.get("chosen_sector")
    sub = data.get("chosen_sub")
    region = data.get("chosen_region")
    j_type = data.get("chosen_job_type")
    salary = data.get("chosen_salary")
    work_time = message.text
    reqs = ", ".join([r.replace("_", " ").capitalize() for r in data.get("selected_reqs", [])])

    # Tadbirkorga ko'rinadigan PREVIEW matni
    preview_text = (
        f"🧐 <b>Ma'lumotlarni tekshiring:</b>\n\n"
        f"🏢 <b>Soha:</b> {sector}\n"
        f"🎯 <b>Yo'nalish:</b> {sub}\n"
        f"📍 <b>Hudud:</b> {region} ({j_type})\n"
        f"💰 <b>Maosh:</b> {salary}\n"
        f"⏰ <b>Ish vaqti:</b> {work_time}\n"
        f"📋 <b>Nomzodga talablar:</b> {reqs}\n\n"
        f"⚠️ <i>Tasdiqlasangiz, e'lon adminga yuboriladi.</i>"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ha, hammasi to'g'ri", callback_data="confirm_ad_final")
    kb.button(text="❌ Bekor qilish", callback_data="cancel_ad_final")
    kb.adjust(1)

    await state.set_state(AdCreation.confirm)
    await message.answer(preview_text, reply_markup=kb.as_markup(), parse_mode="HTML")

# 10. YAKUNIY TASDIQLASH (Adminga yuborish)
@router.callback_query(AdCreation.confirm, F.data == "confirm_ad_final")
async def send_to_admin_final(callback: types.CallbackQuery, state: FSMContext, bot: Bot, db_pool):
    data = await state.get_data()
    user = callback.from_user
    
    # 1. Bazaga saqlash
    async with db_pool.acquire() as conn:
        # Oxirgi kiritilgan ID ni olish uchun 'RETURNING id' ishlatamiz
        ad_id = await conn.fetchval("""
            INSERT INTO ads (owner_id, soha, sub_sector, region, job_type, salary, work_time, selected_reqs, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
            RETURNING id
        """, user.id, data['chosen_sector'], data['chosen_sub'], 
             data['chosen_region'], data['chosen_job_type'], 
             data['chosen_salary'], data['chosen_work_time'], 
             ",".join(data['selected_reqs']))

    # 2. Adminga yuboriladigan xabar dizayni
    reqs_list = ", ".join([r.replace("_", " ").capitalize() for r in data['selected_reqs']])
    admin_text = (
        f"🚀 <b>YANGI E'LON (#ID_{ad_id})</b>\n\n"
        f"👤 <b>Tadbirkor:</b> {user.full_name} (<a href='tg://user?id={user.id}'>Profil</a>)\n"
        f"🏢 <b>Soha:</b> {data['chosen_sector']}\n"
        f"🎯 <b>Yo'nalish:</b> {data['chosen_sub']}\n"
        f"📍 <b>Hudud:</b> {data['chosen_region']} ({data['chosen_job_type']})\n"
        f"💰 <b>Maosh:</b> {data['chosen_salary']}\n"
        f"⏰ <b>Ish vaqti:</b> {data['chosen_work_time']}\n"
        f"📋 <b>Talablar:</b> {reqs_list}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash (Kanalga)", callback_data=f"approve_{user.id}")
    # Rad etish tugmasida ad_id ni ham yuboramiz
    kb.button(text="❌ Rad etish (Sabab bilan)", callback_data=f"reject_ask_{ad_id}_{user.id}")
    kb.adjust(1)

    await bot.send_message(os.getenv("ADMIN_ID"), admin_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    
    await callback.message.edit_text("🚀 <b>Rahmat! E'loningiz adminga yuborildi.</b>", parse_mode="HTML")
    await state.clear()
# 11. BEKOR QILISH
@router.callback_query(AdCreation.confirm, F.data == "cancel_ad_final")
async def cancel_ad(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ <b>E'lon bekor qilindi.</b>", parse_mode="HTML")
    # 1. SEVIMLILARGA QO'SHISH

# --- 1. RAD ETISH (Reject) ---
# Admin rad etish tugmasini bossa
@router.callback_query(F.data.startswith("reject_ask_"))
async def ask_reject_reason(callback: types.CallbackQuery, state: FSMContext):
    # Callbackdan ma'lumotlarni ajratib olamiz: reject_ask_ADID_USERID
    parts = callback.data.split("_")
    ad_id = parts[2]
    user_id = parts[3]

    await state.set_state(AdCreation.reject_reason)
    await state.update_data(reject_ad_id=ad_id, reject_user_id=user_id)

    await callback.message.answer(f"⚠️ <b>ID {ad_id} uchun rad etish sababini yozing:</b>\n"
                                 f"(Tadbirkorga aynan shu matn boradi)")
    await callback.answer()

# Admin sababni yozib yuborsa
@router.message(AdCreation.reject_reason)
async def process_reject_reason(message: types.Message, state: FSMContext, bot: Bot, db_pool):
    if message.from_user.id != int(os.getenv("ADMIN_ID")):
        return # Faqat admin yozishi mumkin

    data = await state.get_data()
    ad_id = int(data['reject_ad_id'])
    user_id = int(data['reject_user_id'])
    reason = message.text

    async with db_pool.acquire() as conn:
        # Statusni bazada yangilash
        await conn.execute("UPDATE ads SET status = 'rejected' WHERE id = $1", ad_id)

    # Tadbirkorga xabar yuborish
    try:
        await bot.send_message(
            user_id, 
            f"❌ <b>Sizning e'loningiz rad etildi.</b>\n\n"
            f"📝 <b>Sabab:</b> {reason}\n\n"
            f"<i>Iltimos, xatolarni to'g'rilab qaytadan urinib ko'ring.</i>",
            parse_mode="HTML"
        )
        await message.answer(f"✅ Sabab tadbirkorga yuborildi.")
    except Exception as e:
        await message.answer(f"⚠️ Tadbirkorga xabar yuborib bo'lmadi (bloklagan bo'lishi mumkin).")

    await state.clear()



# --- 1. BOG'LANISH TUGMASI BOSILGANDA ---
@router.callback_query(F.data.startswith("contact_"))
async def start_contact(callback: types.CallbackQuery, state: FSMContext):
    candidate_id = int(callback.data.split("_")[1])
    await state.update_data(candidate_id=candidate_id)
    
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🎤 Ovozli (Golos)", callback_data="type_voice"),
        types.InlineKeyboardButton(text="📝 Xabar (Uchrashuv)", callback_data="type_text")
    )
    
    await callback.message.answer("Ishchi bilan qanday bog'lanamiz?", reply_markup=kb.as_markup())
    await state.set_state(ContactState.choosing_method)
    await callback.answer()

# --- 2. OVOZLI XABAR VARIANTI ---
@router.callback_query(ContactState.choosing_method, F.data == "type_voice")
async def ask_voice(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎤 Ishchi uchun ovozli xabaringizni yuboring:")
    await state.set_state(ContactState.waiting_voice)

@router.message(ContactState.waiting_voice, F.voice)
async def send_voice_to_candidate(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    
    # Ishchiga yuborish
    await bot.send_message(data['candidate_id'], "📢 <b>Sizga ish beruvchidan ovozli xabar keldi:</b>", parse_mode="HTML")
    await bot.send_voice(data['candidate_id'], message.voice.file_id)
    
    await message.answer("✅ Ovozli xabaringiz yuborildi!")
    await state.clear()

# --- 3. XABAR (UCHRASHUV) VARIANTI ---
@router.callback_query(ContactState.choosing_method, F.data == "type_text")
async def ask_details(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📅 Uchrashuv sanasi va telefon raqamingizni yozing:\n<i>Masalan: Ertaga soat 10:00 da, +998901234567</i>", parse_mode="HTML")
    await state.set_state(ContactState.waiting_details)

@router.message(ContactState.waiting_details)
async def ask_location(message: types.Message, state: FSMContext):
    await state.update_data(meeting_info=message.text)
    
    # Lokatsiya so'rash uchun maxsus tugma
    kb = ReplyKeyboardBuilder()
    kb.button(text="📍 Lokatsiya yuborish", request_location=True)
    
    await message.answer("📍 Endi uchrashuv joyi (lokatsiya)ni yuboring:", 
                         reply_markup=kb.as_markup(resize_keyboard=True, one_time_keyboard=True))
    await state.set_state(ContactState.waiting_location)

# --- 4. YAKUNIY YUBORISH (LOKATSIYA BILAN) ---
@router.message(ContactState.waiting_location, F.location)
async def finalize_contact(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    candidate_id = data['candidate_id']
    info = data['meeting_info']
    
    # Ishchiga (Nomzodga) hamma ma'lumotni yuboramiz
    text_to_cand = (
        "🎉 <b>Sizni uchrashuvga taklif qilishdi!</b>\n\n"
        f"📝 <b>Ma'lumot:</b> {info}\n"
        "📍 <b>Manzil:</b> Pastdagi lokatsiya bo'yicha kelishingiz mumkin."
    )
    
    await bot.send_message(candidate_id, text_to_cand, parse_mode="HTML")
    await bot.send_location(candidate_id, message.location.latitude, message.location.longitude)
    
    await message.answer("✅ Ma'lumotlar ishchiga yuborildi!", reply_markup=types.ReplyKeyboardRemove())
    await state.clear()
# --- 3. SEVIMLILARGA QO'SHISH (Save/Favorite) ---
import json

import json

@router.callback_query(F.data.startswith("fav_"))
async def save_to_favorites(callback: types.CallbackQuery, db_pool, state: FSMContext):
    candidate_id = int(callback.data.split("_")[1])
    owner_id = callback.from_user.id
    
    # 1. State'dan ma'lumotni olishga harakat qilamiz
    state_data = await state.get_data()
    answers = state_data.get('answers', {})

    # 2. Agar state'da ma'lumot bo'lmasa, xabarni o'zidan qidiramiz
    if not answers:
        # Xabar matnini (caption yoki text) tahlil qilish
        msg_text = callback.message.caption if callback.message.caption else callback.message.text
        
        # Ma'lumotlarni matndan ajratib olish (oddiyroq usulda)
        lines = msg_text.split('\n')
        for line in lines:
            if "Ism:" in line: answers['full_name'] = line.split("Ism:")[1].strip()
            if "Yosh:" in line: answers['age'] = line.split("Yosh:")[1].strip()
            if "Tel:" in line: answers['phone'] = line.split("Tel:")[1].strip()
            if "Tajriba:" in line: answers['experience'] = line.split("Tajriba:")[1].strip()
            if "Manzil:" in line: answers['address'] = line.split("Manzil:")[1].strip()

        # Rasm ID-sini olish
        if callback.message.photo:
            answers['photo'] = callback.message.photo[-1].file_id

    # 3. Bazaga yozish
    info_json = json.dumps(answers)
    
    async with db_pool.acquire() as conn:
        # Avval tekshirish
        exists = await conn.fetchval(
            "SELECT id FROM favorites WHERE owner_id = $1 AND candidate_id = $2", 
            owner_id, candidate_id
        )
        if not exists:
            await conn.execute(
                "INSERT INTO favorites (owner_id, candidate_id, info_json) VALUES ($1, $2, $3)",
                owner_id, candidate_id, info_json
            )
            text = "⭐ Nomzod saralanganlarga saqlandi!"
        else:
            text = "⚠️ Bu nomzod allaqachon ro'yxatingizda bor."

    await callback.answer(text, show_alert=True)

@router.callback_query(F.data == "balance")
async def show_balance(callback: types.CallbackQuery, db_pool):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", callback.from_user.id)
    
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="➕ Balansni to'ldirish", callback_data="refill_balance"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="employer_panel"))

    await callback.message.edit_text(
        f"💰 <b>Sizning balansingiz:</b> {user['balance']} ball\n\n"
        f"ℹ️ 1 ta e'lon joylashtirish = 10 ball",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

# To'lov paketlarini yuborish
# TO'LOV PAKETLARI (Tugmalar)
# 1. To'lov paketlarini chiqarish (Tugmalar)
@router.callback_query(F.data == "refill_balance")
async def send_invoice_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    # Callback_data nomlarini xarid_10 ga o'zgartirdik
    kb.row(types.InlineKeyboardButton(text="⭐ 10 ball - 10 000 so'm", callback_data="xarid_10"))
    kb.row(types.InlineKeyboardButton(text="⭐ 30 ball - 30 000 so'm", callback_data="xarid_30"))
    kb.row(types.InlineKeyboardButton(text="⭐ 50 ball - 50 000 so'm", callback_data="xarid_50"))
    kb.row(types.InlineKeyboardButton(text="⭐ 100 ball - 100 000 so'm", callback_data="xarid_100"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="balance"))
    
    await callback.message.edit_text("Kerakli paketni tanlang:", reply_markup=kb.as_markup())

# 2. INVOICE YUBORISH (Nomini xarid_ qildik)
@router.callback_query(F.data.startswith("xarid_"))
async def process_xarid_ball(callback: types.CallbackQuery, bot: Bot):
    try:
        # xarid_10 -> split("_")[1] raqamni beradi
        ball_amount = int(callback.data.split("_")[1]) 
    except:
        return await callback.answer("❌ Xarid ma'lumotida xato!")

    # Narxlar jadvali
    prices_map = {10: 10000, 30: 30000, 50: 50000, 100: 100000}
    selected_price = prices_map.get(ball_amount)

    # Payloadni ham mustahkam qilib refill_ball_10 formatiga keltirdik
    invoice_payload = f"refill_ball_{ball_amount}" 

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"💳 {ball_amount} ball sotib olish",
        description=f"Korgoh tizimi: Hisobingizga {ball_amount} ball qo'shiladi.",
        provider_token=os.getenv("CLICK_TOKEN"),
        currency="UZS",
        prices=[types.LabeledPrice(label=f"{ball_amount} ball", amount=selected_price * 100)],
        payload=invoice_payload, 
        start_parameter="refill",
        is_flexible=False
    )
    await callback.answer()


    # Ixtiyoriy: Admin panelga ham bildirishnoma yuborsang bo'ladi
    # await bot.send_message(ADMIN_ID, f"💰 User {user_id} hisobini {ball_added} ballga to'ldirdi.")
# 1. Sohalarni chiqarish

@router.callback_query(F.data == "employer_panel")
async def back_to_employer_panel(callback: types.CallbackQuery, db_pool):
    user_id = callback.from_user.id
    
    async with db_pool.acquire() as conn:
        # Foydalanuvchiga tegishli xona raqamini olamiz
        # Sening DB strukturang bo'yicha 'rooms' jadvalidan qidiramiz
        room_data = await conn.fetchval(
            "SELECT room_number FROM rooms WHERE owner_id = $1 LIMIT 1", 
            user_id
        )
    
    # Agar xona topilmasa, "Noma'lum" deb chiqaramiz
    room_number = room_data if room_data else "Yo'q"

    # Sening o'sha TAYYOR FUNKSIYANGNI chaqiramiz
    await callback.message.edit_text(
        f"🏠 <b>Tadbirkorlik paneliga xush kelibsiz!</b>\n"
        f"Xonangiz: №{room_number}",
        reply_markup=employer_panel_keyboard(room_number), # Funksiyaga xona raqamini berdik
        parse_mode="HTML"
    )
    await callback.answer()
# 1. Sohalarni chiqarish (Orqaga tugmasi bilan)
@router.callback_query(F.data == "view_my_ads")
async def show_my_sectors(callback: types.CallbackQuery, db_pool):
    async with db_pool.acquire() as conn:
        sectors = await conn.fetch("SELECT DISTINCT soha FROM ads WHERE owner_id = $1", callback.from_user.id)
    
    kb = InlineKeyboardBuilder()
    if not sectors:
        return await callback.answer("Sizda hozircha faol e'lonlar yo'q.", show_alert=True)

    for s in sectors:
        kb.row(types.InlineKeyboardButton(text=f"📁 {s['soha']}", callback_data=f"del_sec_{s['soha']}"))
    
    # Orqaga panelga
    kb.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="employer_panel"))
    
    await callback.message.edit_text("O'chirmoqchi bo'lgan e'loningiz sohasini tanlang:", reply_markup=kb.as_markup())



# 2. Yo'nalishni tanlash (Orqaga tugmasi bilan)
@router.callback_query(F.data.startswith("del_sec_"))
async def show_my_subs_to_delete(callback: types.CallbackQuery, db_pool):
    soha = callback.data.replace("del_sec_", "")
    async with db_pool.acquire() as conn:
        subs = await conn.fetch("SELECT id, sub_sector FROM ads WHERE owner_id = $1 AND soha = $2", 
                                callback.from_user.id, soha)
    
    kb = InlineKeyboardBuilder()
    for sub in subs:
        # Endi to'g'ridan-to'g'ri o'chirmaymiz, tasdiqlashga yuboramiz
        kb.row(types.InlineKeyboardButton(text=f"📍 {sub['sub_sector']}", callback_data=f"confirm_del_{sub['id']}"))
    
    kb.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="view_my_ads"))
    
    await callback.message.edit_text(f"<b>{soha}</b> sohasidagi qaysi e'lonni o'chirmoqchisiz?", 
                                     reply_markup=kb.as_markup(), parse_mode="HTML")

# 3. Tasdiqlash bosqichi (Xavfsizlik filtri)
@router.callback_query(F.data.startswith("confirm_del_"))
async def confirm_delete_ad(callback: types.CallbackQuery, db_pool):
    ad_id = int(callback.data.split("_")[2])
    
    async with db_pool.acquire() as conn:
        # room_number kerak bo'lsa, JOIN orqali uni ham olamiz
        ad = await conn.fetchrow("""
            SELECT a.soha, a.sub_sector, r.room_number 
            FROM ads a
            JOIN rooms r ON a.owner_id = r.owner_id
            WHERE a.id = $1
        """, ad_id)
    
    if not ad:
        return await callback.answer("E'lon topilmadi!")

    # Tasdiqlash tugmalari
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="✅ Ha, o'chirilsin", callback_data=f"final_delete_{ad_id}"),
        types.InlineKeyboardButton(text="❌ Yo'q, qolsin", callback_data="view_my_ads")
    )
    
    # Xatoni to'g'irlash: reply_markup ga yuqoridagi kb ni beramiz
    await callback.message.edit_text(
        text=(
            f"⚠️ <b>DIQQAT!</b>\n\n"
            f"Siz haqiqatdan ham <b>{ad['soha']}</b> -> <b>{ad['sub_sector']}</b> e'lonini o'chirib tashlamoqchimisiz?\n"
            f"Bu amalni ortga qaytarib bo'lmaydi!"
        ),
        reply_markup=kb.as_markup(), # Xatolik shu yerda edi
        parse_mode="HTML"
    )

# 4. Yakuniy o'chirish
@router.callback_query(F.data.startswith("final_delete_"))
async def delete_ad(callback: types.CallbackQuery, db_pool):
    ad_id = int(callback.data.split("_")[2])
    
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM ads WHERE id = $1", ad_id)
    
    await callback.answer("🗑 E'lon muvaffaqiyatli o'chirildi!", show_alert=True)
    # E'lonlar ro'yxatiga qaytaramiz
    await show_my_sectors(callback, db_pool)

@router.callback_query(F.data == "view_favorites")
@router.callback_query(F.data.startswith("fav_page_"))
async def show_favorites_paged(callback: types.CallbackQuery, db_pool, bot: Bot):
    # Sahifa raqamini aniqlash
    current_index = 0
    if callback.data.startswith("fav_page_"):
        current_index = int(callback.data.split("_")[2])

    async with db_pool.acquire() as conn:
        favs = await conn.fetch(
            "SELECT candidate_id, info_json FROM favorites WHERE owner_id = $1 ORDER BY id DESC", 
            callback.from_user.id
        )
    
    if not favs:
        if callback.data == "view_favorites":
            return await callback.answer("⭐ Saralangan nomzodlar hozircha yo'q.", show_alert=True)
        else:
            return await callback.message.edit_text("⭐ Ro'yxat bo'shab qoldi.")

    total_count = len(favs)
    # Hozirgi sahifadagi nomzod ma'lumotlari
    f = favs[current_index]
    data = json.loads(f['info_json'])
    candidate_id = f['candidate_id']
    
    # Matn tayyorlash
    summary = (
        f"⭐ <b>Saralangan nomzod ({current_index + 1}/{total_count})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Nomzod:</b> <a href='tg://user?id={candidate_id}'>Profil</a>\n"
        f"🆔 <b>ID:</b> <code>{candidate_id}</code>\n"
    )
    
    pretty_names = {"full_name": "👤 Ism", "age": "🔢 Yosh", "phone": "📞 Tel", "experience": "⏳ Tajriba", "address": "📍 Manzil"}
    for key, val in data.items():
        if key not in ['photo', 'voice']:
            label = pretty_names.get(key, key.capitalize())
            summary += f"🔹 <b>{label}:</b> {val}\n"

    reply_markup = get_fav_keyboard(candidate_id, current_index, total_count)

    # Media bilan chiqarish (Eski xabarni o'chirib yangisini yuboramiz, chunki rasm bo'lsa edit_text ishlamaydi)
    try:
        # Agar xabar rasm bo'lsa va yangi sahifada ham rasm bo'lsa edit_media qilish mumkin, 
        # lekin soddalik uchun delete va send qilamiz:
        await callback.message.delete()
        
        if 'photo' in data:
            await callback.message.answer_photo(
                photo=data['photo'], caption=summary, 
                reply_markup=reply_markup, parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                summary, reply_markup=reply_markup, parse_mode="HTML"
            )
        
        # Ovozli xabarni faqat so'ralganda yuborish ma'qul, 
        # yoki har safar ostidan yuboriladi (lekin bu biroz noqulay bo'lishi mumkin)
        if 'voice' in data:
            await bot.send_voice(
                callback.from_user.id, data['voice'], 
                caption=f"🎤 {data.get('full_name', '')} - ovozli ma'lumot"
            )
            
    except Exception as e:
        print(f"Pagination xatosi: {e}")

        
@router.callback_query(F.data.startswith("remove_fav_"))
async def remove_favorite(callback: types.CallbackQuery, db_pool):
    parts = callback.data.split("_")
    candidate_id = int(parts[2])
    # current_index = int(parts[3]) # Kerak bo'lsa ishlatish mumkin

    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM favorites WHERE owner_id = $1 AND candidate_id = $2",
            callback.from_user.id, candidate_id
        )
    
    await callback.answer("🗑 Ro'yxatdan o'chirildi.")
    # Ro'yxatni yangilash uchun view_favorites funksiyasini qayta chaqiramiz
    await show_favorites_paged(callback, db_pool, callback.bot)



@router.callback_query(F.data == "emp_settings")
async def employer_settings(callback: types.CallbackQuery, db_pool):
    user_id = callback.from_user.id
    
    async with db_pool.acquire() as conn:
        # Tadbirkorning joriy sozlamalarini olamiz
        settings = await conn.fetchrow(
            "SELECT balance, (SELECT COUNT(*) FROM ads WHERE owner_id = $1) as ads_count FROM users WHERE user_id = $1", 
            user_id
        )

    text = (
        "⚙️ **Boshqaruv va Sozlamalar**\n\n"
        f"📊 **Statistika:**\n"
        f"└ Jami e'lonlaringiz: {settings['ads_count']} ta\n"
        f"└ Joriy balans: {settings['balance'] or 0} ⭐\n\n"
        "🔧 **Funksiyalar:**\n"
        "• Bildirishnomalarni boshqarish\n"
        "• Avto-javob matnini sozlash\n"
        "• Ish vaqtini belgilash"
    )

    kb = InlineKeyboardBuilder()
    # Noo'tdiy tugmalar
    kb.row(types.InlineKeyboardButton(text="🔔 Bildirishnomalar: ✅ ON", callback_data="toggle_notif"))
    kb.row(types.InlineKeyboardButton(text="💬 Avto-javob matni", callback_data="set_auto_reply"))
    kb.row(types.InlineKeyboardButton(text="📈 Batafsil statistika", callback_data="view_analytics"))
    # emp_settings ichidagi builderga qo'shiladi
    kb.row(types.InlineKeyboardButton(text="🗑 Profilni o'chirish", callback_data="delete_profile_start"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="employer_panel"))
    
    kb.adjust(1, 1, 1, 1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="Markdown")


@router.callback_query(F.data == "view_analytics")
async def view_analytics(callback: types.CallbackQuery, db_pool):
    user_id = callback.from_user.id
    
    async with db_pool.acquire() as conn:
        # E'lonlar bo'yicha ko'rishlar sonini hisoblaymiz
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_ads,
                SUM(view_count) as total_views,
                (SELECT COUNT(*) FROM favorites WHERE owner_id = $1) as saved_candidates
            FROM ads WHERE owner_id = $1
        """, user_id)

    text = (
        "📈 **Batafsil Analitika**\n\n"
        f"📢 Jami e'lonlar: {stats['total_ads']} ta\n"
        f"👁 Ko'rishlar soni: {stats['total_views'] or 0} marta\n"
        f"⭐ Saqlangan nomzodlar: {stats['saved_candidates']} ta\n\n"
        "ℹ️ _Statistika real vaqt rejimida yangilanadi._"
    )
    
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="emp_settings"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="Markdown")



@router.callback_query(F.data == "delete_profile_start")
async def confirm_delete_profile(callback: types.CallbackQuery):
    text = (
        "⚠️ <b>DIQQAT: QAYTARIB BO'LMAS AMAL!</b>\n\n"
        "Profilni o'chirsangiz, quyidagi ma'lumotlar <b>butunlay yo'qoladi:</b>\n"
        "• Siz sotib olgan barcha xona raqamlari\n"
        "• Barcha e'lonlaringiz va statistikalar\n"
        "• Hisobingizdagi mavjud ballar (yulduzlar)\n"
        "• Saqlangan barcha nomzodlar\n\n"
        "<i>Tizimda siz haqingizda hech qanday ma'lumot qolmaydi. Buni tasdiqlaysizmi?</i>"
    )
    
    kb = InlineKeyboardBuilder()
    # Noo'tdiy usul: "Ha" tugmasini pastga, "Yo'q"ni tepaga qo'yamiz (xatolikni oldini olish uchun)
    kb.row(types.InlineKeyboardButton(text="❌ Yo'q, bekor qilish", callback_data="emp_settings"))
    kb.row(types.InlineKeyboardButton(text="🗑 HA, HAMMASINI O'CHIRISH", callback_data="delete_profile_final"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "delete_profile_final")
async def delete_profile_execution(callback: types.CallbackQuery, db_pool, state: FSMContext):
    user_id = callback.from_user.id
    
    async with db_pool.acquire() as conn:
        # Transaction ishlatamiz - yo hamma narsa o'chsin, yo hech narsa
        async with conn.transaction():
            # 1. E'lonlarni o'chirish
            await conn.execute("DELETE FROM ads WHERE owner_id = $1", user_id)
            # 2. Xonalarni o'chirish (Xonalar bo'shaydi)
            await conn.execute("DELETE FROM rooms WHERE owner_id = $1", user_id)
            # 3. Foydalanuvchining o'zini o'chirish
            await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)

    # State'ni tozalaymiz
    await state.clear()
    
    await callback.message.edit_text(
        "👋 <b>Hisobingiz muvaffaqiyatli o'chirildi.</b>\n\n"
        "Siz bilan hamkorlik qilganimizdan xursandmiz. Yana qaytib kelishingizni kutamiz!",
        parse_mode="HTML"
    )
    
    # Foydalanuvchiga /start tugmasini qaytarib ko'rsatish
    await callback.answer("Profil o'chirildi", show_alert=True)













