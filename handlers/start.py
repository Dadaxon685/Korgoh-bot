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
from aiogram.fsm.state import State, StatesGroup
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
from states.states import EmployerReg # Holatni import qiling
from aiogram.fsm.context import FSMContext

# ... (eski kodlar)

@router.message(F.text == "🏢 Tadbirkorlar zali (Ish beruvchi)")
async def emp_reg(message: types.Message, bot: Bot, state: FSMContext):
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
    await state.set_state(EmployerReg.waiting_name) # ISMNI KUTISH BOSHLANDI

# --- ISMNI QABUL QILISH VA TELEFON SO'RASH ---
@router.message(EmployerReg.waiting_name)
async def process_emp_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text) # Ismni xotiraga saqlaymiz
    
    # Telefon so'rash uchun tugma
    builder = ReplyKeyboardBuilder()
    builder.button(text="📞 Telefon raqamni yuborish", request_contact=True)
    
    await message.answer(
        f"🤝 Tanishganimdan xursandman, <b>{message.text}</b>!\n\n"
        "Endi pastdagi tugmani bosish orqali telefon raqamingizni tasdiqlang:",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="HTML"
    )
    await state.set_state(EmployerReg.waiting_phone) # RAQAMNI KUTISH

# --- RAQAMNI QABUL QILISH VA TARIFLARGA O'TISH ---
@router.message(EmployerReg.waiting_phone, F.contact)
async def process_contact(message: types.Message, state: FSMContext, db_pool, bot: Bot):
    user_id = message.from_user.id
    phone = message.contact.phone_number
    
    # State'dan ismni olamiz
    user_data = await state.get_data()
    full_name = user_data.get("full_name", message.from_user.full_name)

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, full_name, phone, role)
            VALUES ($1, $2, $3, 'employer')
            ON CONFLICT (user_id) DO UPDATE SET phone = $3, role = 'employer', full_name = $2
        """, user_id, full_name, phone)

    await message.answer(
        "📝 <b>Kotiba:</b>\n"
        "<blockquote>\"Rahmat. Ma'lumotlaringiz muhrlandi. Raqamingiz tasdiqlandi.\"</blockquote>", 
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    
    await asyncio.sleep(1)
    await state.clear() # Holatni tozalaymiz

    await message.answer(
        "✅ <b>RO'YXATDAN O'TISH YAKUNLANDI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👨‍💼 <b>Administrator:</b>\n"
        "<blockquote>\"Marhamat, endi o'zingizga ma'qul <b>Ofis (Tarif)</b> turini tanlang:\"</blockquote>",
        reply_markup=room_types_keyboard(),
        parse_mode="HTML"
    )




from aiogram.types import ReplyKeyboardRemove
from keyboards.inlines import candidate_panel_keyboard # Panel klaviaturasini import qiling

@router.message(F.text == "🔍 Kadrlar bo'limi (Nomzod)")
async def candidate_registration(message: types.Message, db_pool, bot: Bot):
    user_id = message.from_user.id
    full_name = message.from_user.full_name # Telegramdagi ismini olamiz

    # 1. Lift effekti (Sizning uslubingizda)
    await bot.send_chat_action(chat_id=message.chat.id, action="find_location")
    status = await message.answer("🪜 <b>Eskalator:</b> <i>2-qavat, Kadrlar bo'limiga tushmoqdasiz...</i>", parse_mode="HTML")
    await asyncio.sleep(1.2)
    await status.delete()

    # 2. Ma'lumotlar bazasiga saqlash (Rolini 'candidate' qilish)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, full_name, role)
            VALUES ($1, $2, 'candidate')
            ON CONFLICT (user_id) DO UPDATE SET role = 'candidate', full_name = $2
        """, user_id, full_name)

    # 3. Muvaffaqiyatli xabar va Panelni ochish
    welcome_text = (
        "🏢 <b>KADRLAR BO'LIMI | REGISTRATURA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👩‍💼 <b>Kadrlar menejeri:</b>\n"
        f"<blockquote>\"Xush kelibsiz, <b>{full_name}</b>! Ma'lumotlaringiz tizimga kiritildi. "
        "Siz muvaffaqiyatli <b>Ish izlovchi</b> sifatida ro'yxatdan o'tdingiz.\"</blockquote>\n"
        "✅ <b>Holatingiz:</b> <code>Aktiv Nomzod</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>Quyidagi menyu orqali bo'sh ish o'rinlarini qidirishingiz mumkin:</b>"
    )

    await message.answer(
        welcome_text, 
        reply_markup=candidate_panel_keyboard(), # Nomzod panelini chiqaradi
        parse_mode="HTML"
    )
    
    # Eskidan qolgan Reply tugmalarni o'chirib tashlaymiz
    # Agar reply_markup=ReplyKeyboardRemove() ishlamasa, alohida xabar yuborsa ham bo'ladi
