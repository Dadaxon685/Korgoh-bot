from aiogram import Router, F, types, Bot
# --- 2. BOG'LANISH (Contact/Accept) ---
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from states.states import ContactState
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

router = Router()

# --- 1. RAD ETISH (Reject) ---
@router.callback_query(F.data.startswith("rej_cand_"))
async def reject_candidate(callback: types.CallbackQuery, bot: Bot):
    candidate_id = int(callback.data.split("_")[2])
    
    # Tadbirkorga javob
    await callback.message.edit_text(
        f"{callback.message.text}\n\n❌ <b>Rad etildi</b>", 
        parse_mode="HTML"
    )
    
    # Nomzodga xabar yuborish
    try:
        await bot.send_message(
            candidate_id, 
            "😔 Kechirasiz, sizning anketangiz ish beruvchiga ma'qul kelmadi. Boshqa vakansiyalarni ko'rib chiqing."
        )
    except:
        pass
    await callback.answer("Nomzodga rad javobi yuborildi.")



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

@router.message(ContactState.waiting_voice, F.voice)
async def send_voice_to_candidate(message: types.Message, state: FSMContext, bot: Bot, db_pool):
    data = await state.get_data()
    candidate_id = data.get('candidate_id')
    owner_id = message.from_user.id # Tadbirkorning ID-si

    # 1. Bazadan tadbirkorning xona raqamini olamiz
    async with db_pool.acquire() as conn:
        room = await conn.fetchrow(
            "SELECT room_number FROM rooms WHERE owner_id = $1 LIMIT 1", 
            owner_id
        )
    
    # Agar xona raqami topilmasa, "Noma'lum" deb ketadi
    room_num = room['room_number'] if room else "Noma'lum"

    # 2. Ishchiga (nomzodga) xabar yuborish
    try:
        header_text = (
            f"📢 <b>Sizga ish beruvchidan ovozli xabar keldi!</b>\n"
            f"🔢 <b>Xona raqami:</b> <code>{room_num}</code>"
        )
        
        await bot.send_message(candidate_id, header_text, parse_mode="HTML")
        await bot.send_voice(candidate_id, message.voice.file_id)
        
        # 3. Tadbirkorga tasdiqlash
        await message.answer(f"✅ Ovozli xabaringiz {room_num}-xona nomidan yuborildi!")
        
    except Exception as e:
        await message.answer("❌ Xabar yuborishda xatolik: Ishchi botni bloklagan bo'lishi mumkin.")
        print(f"Voice send error: {e}")

    await state.clear()
# --- 3. XABAR (UCHRASHUV) VARIANTI ---
# --- 3. XABAR (UCHRASHUV) VARIANTI ---
@router.callback_query(ContactState.choosing_method, F.data == "type_text")
async def ask_details(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📅 <b>Uchrashuv ma'lumotlarini yozing:</b>\n\n"
        "<i>Masalan: Ertaga soat 10:00 da kuting, tel: +998901234567</i>", 
        parse_mode="HTML"
    )
    await state.set_state(ContactState.waiting_details)

@router.message(ContactState.waiting_details)
async def ask_location(message: types.Message, state: FSMContext):
    await state.update_data(meeting_info=message.text)
    
    # Lokatsiya so'rash uchun maxsus tugma
    kb = ReplyKeyboardBuilder()
    kb.button(text="📍 Lokatsiya yuborish", request_location=True)
    
    await message.answer(
        "📍 Endi uchrashuv joyi (lokatsiya)ni yuboring:", 
        reply_markup=kb.as_markup(resize_keyboard=True, one_time_keyboard=True)
    )
    await state.set_state(ContactState.waiting_location)

# --- 4. YAKUNIY YUBORISH (LOKATSIYA BILAN) ---
@router.message(ContactState.waiting_location, F.location)
async def finalize_contact(message: types.Message, state: FSMContext, bot: Bot, db_pool):
    data = await state.get_data()
    candidate_id = data.get('candidate_id')
    info = data.get('meeting_info')
    owner_id = message.from_user.id

    # 1. Bazadan tadbirkorning xona raqamini olamiz
    async with db_pool.acquire() as conn:
        room = await conn.fetchrow(
            "SELECT room_number FROM rooms WHERE owner_id = $1 LIMIT 1", 
            owner_id
        )
    
    room_num = room['room_number'] if room else "Noma'lum"

    # 2. Ishchiga (Nomzodga) hamma ma'lumotni yuboramiz
    text_to_cand = (
        f"🎉 <b>Sizni uchrashuvga taklif qilishdi!</b>\n\n"
        f"🔢 <b>Xona raqami:</b> <code>{room_num}</code>\n"
        f"📝 <b>Ma'lumot:</b> {info}\n\n"
        f"📍 <b>Manzil:</b> Pastdagi lokatsiya bo'yicha kelishingiz mumkin."
    )
    
    try:
        # Xabarni va lokatsiyani yuboramiz
        await bot.send_message(candidate_id, text_to_cand, parse_mode="HTML")
        await bot.send_location(
            candidate_id, 
            latitude=message.location.latitude, 
            longitude=message.location.longitude
        )
        
        # 3. Tadbirkorga tasdiqlash va knopkani o'chirish
        await message.answer(
            f"✅ Ma'lumotlar va lokatsiya {room_num}-xona nomidan yuborildi!", 
            reply_markup=types.ReplyKeyboardRemove()
        )
        
    except Exception as e:
        await message.answer(
            "❌ Xatolik: Nomzod botni bloklagan bo'lishi mumkin.", 
            reply_markup=types.ReplyKeyboardRemove()
        )
        print(f"Finalize contact error: {e}")

    await state.clear()
# --- 3. SEVIMLILARGA QO'SHISH (Save/Favorite) ---
@router.callback_query(F.data.startswith("fav_"))
async def save_to_favorites(callback: types.CallbackQuery, db_pool):
    candidate_id = int(callback.data.split("_")[1])
    employer_id = callback.from_user.id
    
    # Bu yerda ma'lumotni bazaga saqlash mantiqi (ixtiyoriy)
    # Masalan: favorites degan jadvalga yozish mumkin
    
    await callback.answer("⭐ Nomzod sevimlilar ro'yxatiga qo'shildi (Saralandi)!")
    await callback.message.edit_text(
        f"{callback.message.text}\n\n⭐️ <b>Saralanganlarda</b>", 
        parse_mode="HTML"
    )