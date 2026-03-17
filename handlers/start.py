import os
import asyncio
from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# Keyboards importlari
from keyboards.inlines import (
    employer_panel_keyboard, 
    candidate_panel_keyboard, 
    admin_panel_keyboard,
    room_types_keyboard
)

router = Router()

# 1. Holatlarni (States) e'lon qilish
class Registration(StatesGroup):
    waiting_for_employer_name = State()
    waiting_for_candidate_name = State()

@router.message(CommandStart())
async def cmd_start(message: types.Message, db_pool, bot: Bot):
    user_id = message.from_user.id
    admin_id = os.getenv("ADMIN_ID")

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    await asyncio.sleep(0.5)

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT u.role, r.room_number, r.room_type 
            FROM users u
            LEFT JOIN rooms r ON u.user_id = r.owner_id 
            WHERE u.user_id = $1
        """, user_id)

    # Foydalanuvchi bazada bo'lsa
    if user:
        current_role = user['role']
        room_num = user['room_number']
        room_type = (user['room_type'] or "Standart").capitalize()

        if str(user_id) == str(admin_id):
            return await message.answer("🏙 <b>KORGOH_UZ | NAZORAT MINORASI</b>\n...", reply_markup=admin_panel_keyboard(), parse_mode="HTML")

        if current_role == 'employer':
            if room_num:
                return await message.answer(f"🏢 <b>{room_num}-XONA | TADBIRKOR OFISI</b>\n...", reply_markup=employer_panel_keyboard(room_num), parse_mode="HTML")
            else:
                return await message.answer("🏙 <b>KORGOH MARKAZI | QABULXONA</b>\n...", reply_markup=room_types_keyboard(), parse_mode="HTML")

        if current_role == 'candidate':
            return await message.answer("🏢 <b>KADRLAR BO'LIMI | 2-QAVAT</b>\n...", reply_markup=candidate_panel_keyboard(), parse_mode="HTML")

    # Yangi foydalanuvchi uchun
    main_text = (
        "🏙 <b>KORGOH_UZ MUHTASHAM BIZNES MARKAZI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👨‍✈️ <b>Qorovul:</b>\n"
        "<blockquote>\"Assalomu alaykum, mehmon! Qaysi qavatga chiqishda yordam berishim mumkin?\"</blockquote>"
    )
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="🏢 Tadbirkorlar zali (Ish beruvchi)")
    builder.button(text="🔍 Kadrlar bo'limi (Nomzod)")
    builder.adjust(1)

    await message.answer(main_text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="HTML")

# --- 2. ISH BERUVCHI (EMPLOYER) REGISTRATSIYASI ---

@router.message(F.text == "🏢 Tadbirkorlar zali (Ish beruvchi)")
async def emp_reg(message: types.Message, bot: Bot, state: FSMContext):
    await state.set_state(Registration.waiting_for_employer_name)
    
    status = await message.answer("🛗 <b>Lift:</b> <i>10-qavatga ko'tarilmoqdasiz...</i>", parse_mode="HTML")
    await asyncio.sleep(1)
    await status.delete()

    await message.answer("💼 <b>TADBIRKORLAR QAVATI</b>\n📌 <b>Ismingizni kiriting:</b>", parse_mode="HTML")

@router.message(Registration.waiting_for_employer_name)
async def process_employer_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text) # Ism xotirada qoladi
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Kontaktni yuborish", request_contact=True)
    
    await message.answer(
        f"🤝 Rahmat, <b>{message.text}</b>!\nEndi kontaktingizni yuboring:",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="HTML"
    )
    # MUHIM: Bu yerda state.clear() qilmaymiz, chunki kontakt kelishini kutamiz!

# --- 3. NOMZOD (CANDIDATE) REGISTRATSIYASI ---

@router.message(F.text == "🔍 Kadrlar bo'limi (Nomzod)")
async def cand_reg(message: types.Message, bot: Bot, state: FSMContext):
    await state.set_state(Registration.waiting_for_candidate_name)
    
    status = await message.answer("🪜 <b>Eskalator:</b> <i>2-qavatga chiqmoqdasiz...</i>", parse_mode="HTML")
    await asyncio.sleep(1)
    await status.delete()

    await message.answer("👤 <b>KADRLAR BO'LIMI</b>\n📌 <b>Ism va familiyangizni kiriting:</b>", parse_mode="HTML")

@router.message(Registration.waiting_for_candidate_name)
async def process_candidate_name(message: types.Message, state: FSMContext, db_pool):
    full_name = message.text
    user_id = message.from_user.id
    
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, full_name, role)
            VALUES ($1, $2, 'candidate')
            ON CONFLICT (user_id) DO UPDATE SET full_name = $2, role = 'candidate'
        """, user_id, full_name)

    await message.answer(f"✅ <b>{full_name}</b>, ro'yxatdan o'tdingiz!", reply_markup=candidate_panel_keyboard(), parse_mode="HTML")
    await state.clear()

# --- 4. KONTAKT QABUL QILISH (ISH BERUVCHI UCHUN YAKUNIY QADAM) ---

@router.message(F.contact)
async def process_contact(message: types.Message, db_pool, state: FSMContext):
    data = await state.get_data()
    full_name = data.get("full_name", message.from_user.full_name)
    user_id = message.from_user.id
    phone = message.contact.phone_number

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, full_name, phone, role)
            VALUES ($1, $2, $3, 'employer')
            ON CONFLICT (user_id) DO UPDATE SET phone = $3, role = 'employer', full_name = $2
        """, user_id, full_name, phone)

    await state.clear() # Endi xotirani tozalash mumkin
    
    await message.answer("📝 Ma'lumotlar saqlandi.", reply_markup=ReplyKeyboardRemove())
    await message.answer("✅ <b>RO'YXATDAN O'TISH YAKUNLANDI</b>\nOfis tanlang:", reply_markup=room_types_keyboard(), parse_mode="HTML")
