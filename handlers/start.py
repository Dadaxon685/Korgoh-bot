import os
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove
from keyboards.inlines import (
    employer_panel_keyboard, 
    candidate_panel_keyboard, 
    admin_panel_keyboard,
    room_types_keyboard
)


from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

class Registration(StatesGroup):
    waiting_for_employer_name = State()
    waiting_for_candidate_name = State()
router = Router()

import asyncio
import os
from aiogram import types, Router, F, Bot


@router.message(CommandStart())
async def cmd_start(message: types.Message, db_pool, bot: Bot):
    user_id = message.from_user.id
    admin_id = os.getenv("ADMIN_ID")

    # --- 1. JONLI EFFEKT (Qorovul yaqinlashmoqda...) ---
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    await asyncio.sleep(1.2)

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT u.role, r.room_number, r.room_type 
            FROM users u
            LEFT JOIN rooms r ON u.user_id = r.owner_id 
            WHERE u.user_id = $1
        """, user_id)

    # --- 2. AGAR FOYDALANUVCHI BAZADA BO'LSA (Tizimga kirish) ---
    if user:
        current_role = user['role']
        room_num = user['room_number']
        room_type = (user['room_type'] or "Standart").capitalize()

        # 👑 ADMINISTRATOR (Bosh boshqaruv minorasi)
        if str(user_id) == str(admin_id):
            admin_text = (
                "🏙 <b>KORGOH_UZ | NAZORAT MINORASI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "🛰 <b>Tizim operatori:</b>\n"
                "<blockquote>\"Xush kelibsiz, Bosh Administrator! Tizimlar barqaror ishlamoqda. "
                "Barcha qavatlar nazorat ostida. Qaysi bo'limni ko'zdan kechiramiz?\"</blockquote>\n"
                "📊 <b>Boshqaruv paneli yuklandi...</b>"
            )
            return await message.answer(admin_text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")

        # 💼 TADBIRKOR (Shaxsiy ofis)
        if current_role == 'employer':
            if room_num:
                text = (
                    f"🏢 <b>{room_num}-XONA | TADBIRKOR OFISI</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "👨‍💼 <b>Shaxsiy yordamchi:</b>\n"
                    f"<blockquote>\"Xush kelibsiz! Siz hozirda <b>{room_type}</b> qavatidagi "
                    f"shaxsiy ofisingizdasiz. Nomzodlar anketalari saralanmoqda.\"</blockquote>\n"
                    "📉 <b>Ofis holati:</b> <code>Aktiv</code> ✅\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "👇 <b>Amallarni tanlang:</b>"
                )
                return await message.answer(text, reply_markup=employer_panel_keyboard(room_num), parse_mode="HTML")
            else:
                text = (
                    "🏙 <b>KORGOH MARKAZI | QABULXONA</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚠️ <b>Ma'lumot xabari:</b>\n"
                    "<blockquote>\"Janob, sizda hali shaxsiy ofis mavjud emas. E'lon joylashtirish uchun "
                    "avval binodan xona ijaraga olishingiz kerak bo'ladi.\"</blockquote>\n"
                    "👇 <b>Marhamat, tariflar bilan tanishing:</b>"
                )
                return await message.answer(text, reply_markup=room_types_keyboard(), parse_mode="HTML")

        # 👤 NOMZOD (Kadrlar bo'limi)
        if current_role == 'candidate':
            re_welcome = (
                "🏢 <b>KADRLAR BO'LIMI | 2-QAVAT</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "👩‍💼 <b>Kadrlar menejeri:</b>\n"
                f"<blockquote>\"Assalomu alaykum, <b>{message.from_user.first_name}</b>! "
                "Yana ko'rib turganimdan xursandman. Bugun siz uchun yangi ish e'lonlari bor.\"</blockquote>\n"
                "🔍 <b>Vakansiyalar yangilandi...</b>"
            )
            return await message.answer(re_welcome, reply_markup=candidate_panel_keyboard(), parse_mode="HTML")

    # --- 3. YANGI FOYDALANUVCHI UCHUN (Birinchi marta kelganda) ---
    main_text = (
        "🏙 <b>KORGOH_UZ MUHTASHAM BIZNES MARKAZI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Bino darvozalari sekin ochildi... Sizni salqin va hashamatli zal qarshi oldi.</i>\n\n"
        "👨‍✈️ <b>Qorovul:</b>\n"
        "<blockquote>\"Assalomu alaykum, mehmon! Bizning markazimizga xush kelibsiz. "
        "Bu yerda tadbirkorlar o'z jamoasini tuzadi, ishchilar esa orzusidagi ishni topadi.\"</blockquote>\n\n"
        "🏛 <b>Sizga qaysi qavatga chiqishda yordam berishim mumkin?</b>"
    )
    
    # Vizual tugmalar (Reply)
    builder = ReplyKeyboardBuilder()
    builder.button(text="🏢 Tadbirkorlar zali (Ish beruvchi)")
    builder.button(text="🔍 Kadrlar bo'limi (Nomzod)")
    builder.adjust(1)

    await message.answer(
        main_text, 
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="HTML"
    )

# --- 4. TUGMALAR BOSILGANDA LIFT VA ESKALATOR EFFEKTI ---

# --- 4. TUGMALAR BOSILGANDA LIFT VA ESKALATOR EFFEKTI ---

@router.message(F.text == "🏢 Tadbirkorlar zali (Ish beruvchi)")
async def emp_reg(message: types.Message, bot: Bot, state: FSMContext):
    await state.set_state(Registration.waiting_for_employer_name) # Holatni o'rnatish
    
    await bot.send_chat_action(chat_id=message.chat.id, action="upload_document")
    status = await message.answer("🛗 <b>Lift:</b> <i>10-qavatga ko'tarilmoqdasiz...</i>", parse_mode="HTML")
    await asyncio.sleep(1.2)
    await status.delete()

    await message.answer(
        "💼 <b>TADBIRKORLAR QAVATI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👩‍💻 <b>Kotiba:</b>\n"
        "<blockquote>\"Xush kelibsiz! Binomizda ofis ochish uchun avval ro'yxatdan o'tishingiz kerak.\"</blockquote>\n"
        "📌 <b>Ismingizni kiriting:</b>", 
        parse_mode="HTML"
    )

# ISMNI QABUL QILISH (Ish beruvchi uchun)
@router.message(Registration.waiting_for_employer_name)
async def process_employer_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text) # Ismni saqlab qo'yamiz
    
    # Kontakt yuborish tugmasini chiqarish
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Kontaktni yuborish", request_contact=True)
    
    await message.answer(
        f"🤝 Rahmat, <b>{message.text}</b>!\n"
        "Endi siz bilan bog'lanishimiz uchun kontaktingizni yuboring:",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="HTML"
    )
    await state.clear() # Yoki keyingi bosqichga o'tkazish

@router.message(F.text == "🔍 Kadrlar bo'limi (Nomzod)")
async def cand_reg(message: types.Message, bot: Bot, state: FSMContext):
    await state.set_state(Registration.waiting_for_candidate_name) # Holatni o'rnatish
    
    await bot.send_chat_action(chat_id=message.chat.id, action="find_location")
    status = await message.answer("🪜 <b>Eskalator:</b> <i>2-qavatga chiqmoqdasiz...</i>", parse_mode="HTML")
    await asyncio.sleep(1.2)
    await status.delete()

    await message.answer(
        "👤 <b>NOMZODLARNI QABUL QILISH ZALI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👨‍💼 <b>Maslahatchi:</b>\n"
        "<blockquote>\"Salom! Ish qidiryapsizmi? To'g'ri joyga keldingiz. Ro'yxatdan o'ting va "
        "tadbirkorlar siz bilan bog'lanishini kuting!\"</blockquote>\n"
        "📌 <b>Ism va familiyangizni kiriting:</b>", 
        parse_mode="HTML"
    )

# ISMNI QABUL QILISH (Nomzod uchun)
@router.message(Registration.waiting_for_candidate_name)
async def process_candidate_name(message: types.Message, state: FSMContext, db_pool: any):
    full_name = message.text
    user_id = message.from_user.id
    
    # Nomzodni bazaga yozish
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, full_name, role)
            VALUES ($1, $2, 'candidate')
            ON CONFLICT (user_id) DO UPDATE SET full_name = $2, role = 'candidate'
        """, user_id, full_name)

    await message.answer(
        f"✅ <b>{full_name}</b>, siz muvaffaqiyatli ro'yxatdan o'tdingiz!\n"
        "Endi nomzodlar panelidan foydalanishingiz mumkin.",
        reply_markup=candidate_panel_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()
