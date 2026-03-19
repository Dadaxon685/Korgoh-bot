import json
import logging
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.inlines import candidate_panel_keyboard, candidate_settings_keyboard
from states.states import JobSeeker, CandidateProfile

router = Router()

# =====================================================
# 1-QISM: ISH QIDIRISH (XONA RAQAMINI SO'RASH)
# =====================================================

@router.callback_query(F.data == "find_job")
async def ask_room_number(callback: types.CallbackQuery, state: FSMContext):
    # Avvalgi state ma'lumotlarini tozalaymiz (muhim!)
    await state.clear()
    await state.set_state(JobSeeker.waiting_room_num)

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="candidate_panel"))

    await callback.message.edit_text(
        "🔢 <b>Xona raqamini kiriting:</b>\n\n"
        "<i>Ish beruvchi bergan 4 xonali raqamni yozing:</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


# =====================================================
# 2-QISM: XONA RAQAMI YOZILSA - SOHALARNI CHIQARISH
# =====================================================

@router.message(JobSeeker.waiting_room_num)
async def process_room_and_show_sectors(message: types.Message, state: FSMContext, db_pool):
    room_num = message.text.strip()

    async with db_pool.acquire() as conn:
        sectors = await conn.fetch("""
            SELECT DISTINCT a.soha
            FROM ads a
            JOIN rooms r ON a.owner_id = r.owner_id
            WHERE r.room_number = $1 AND a.status = 'approved'
        """, room_num)

    if not sectors:
        return await message.answer(
            "❌ Bu xonada faol e'lonlar topilmadi. Raqamni tekshirib qayta yozing."
        )

    await state.update_data(current_room=room_num)

    kb = InlineKeyboardBuilder()
    for row in sectors:
        kb.row(types.InlineKeyboardButton(
            text=f"📁 {row['soha']}",
            callback_data=f"room_sec_{row['soha']}"
        ))
    kb.row(types.InlineKeyboardButton(text="⬅️ Qayta terish", callback_data="find_job"))

    await message.answer(
        f"✅ Xona {room_num} topildi.\nSohani tanlang:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(JobSeeker.choosing_sector)


# =====================================================
# 3-QISM: SOHA TANLANSA - YO'NALISHLARNI CHIQARISH
# =====================================================

@router.callback_query(JobSeeker.choosing_sector, F.data.startswith("room_sec_"))
async def show_room_subs(callback: types.CallbackQuery, state: FSMContext, db_pool):
    soha_name = callback.data.replace("room_sec_", "")
    data = await state.get_data()
    room_num = data['current_room']

    await state.update_data(chosen_sector=soha_name)

    async with db_pool.acquire() as conn:
        subs = await conn.fetch("""
            SELECT DISTINCT a.sub_sector
            FROM ads a
            JOIN rooms r ON a.owner_id = r.owner_id
            WHERE r.room_number = $1 AND a.soha = $2 AND a.status = 'approved'
        """, room_num, soha_name)

    kb = InlineKeyboardBuilder()
    for row in subs:
        kb.row(types.InlineKeyboardButton(
            text=f"📍 {row['sub_sector']}",
            callback_data=f"room_sub_{row['sub_sector']}"
        ))
    kb.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="find_job"))

    await callback.message.edit_text(
        f"🏢 <b>{soha_name}</b> bo'yicha yo'nalishni tanlang:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(JobSeeker.choosing_sub)


# =====================================================
# 4-QISM: YO'NALISH TANLANSA - SAVOLLARNI BOSHLASH
# =====================================================

@router.callback_query(JobSeeker.choosing_sub, F.data.startswith("room_sub_"))
async def start_survey(callback: types.CallbackQuery, state: FSMContext, db_pool):
    sub_name = callback.data.replace("room_sub_", "")
    data = await state.get_data()
    room_num = data['current_room']
    soha_name = data['chosen_sector']

    async with db_pool.acquire() as conn:
        ad = await conn.fetchrow("""
            SELECT a.owner_id, a.selected_reqs
            FROM ads a
            JOIN rooms r ON a.owner_id = r.owner_id
            WHERE r.room_number = $1 AND a.soha = $2
                  AND a.sub_sector = $3 AND a.status = 'approved'
            ORDER BY a.id DESC LIMIT 1
        """, room_num, soha_name, sub_name)

    if not ad:
        return await callback.answer("❌ E'lon topilmadi!", show_alert=True)

    reqs = ad['selected_reqs'].split(",")
    await state.update_data(
        all_reqs=reqs,
        current_step=0,
        target_owner=ad['owner_id'],
        direction=sub_name,
        answers={}
    )

    await callback.message.answer(
        f"🚀 {sub_name} uchun anketani to'ldirish boshlandi."
    )
    await state.set_state(JobSeeker.filling_form)
    await ask_next_step(callback.message, state)


# =====================================================
# 5-QISM: SAVOLLARNI BERUVCHI YORDAMCHI FUNKSIYA
# =====================================================

async def ask_next_step(message: types.Message, state: FSMContext):
    data = await state.get_data()
    reqs = data['all_reqs']
    step = data['current_step']

    if step < len(reqs):
        current_req = reqs[step].strip()

        questions = {
            "full_name": "✍️ Ism va familiyangizni kiriting:",
            "age": "🔢 Tug'ilgan yilingiz yoki yoshingizni kiriting:",
            "phone": "📞 Telefon raqamingizni yuboring yoki kiriting:",
            "photo": "🖼 Rasmingizni yuboring (3x4 formatda bo'lsa yaxshi):",
            "voice": "🎤 O'zingiz haqingizda ovozli xabar yuboring:",
            "experience": "⏳ Ish tajribangiz haqida batafsil ma'lumot bering:",
            "address": "📍 Yashash manzilingizni kiriting (tuman, mahalla):",
            "languages": "🌐 Qaysi tillarni bilasiz? (Masalan: O'zbek, Rus, Ingliz):",
            "education": "🎓 Ma'lumotingiz darajasi qanday? (Oliy, o'rta-maxsus va h.k.):",
            "expected_salary": "💰 Qancha miqdorda maosh (oylik) kutayapsiz?",
            "portfolio": "📁 Portfolioingizni yuboring (link yoki fayl ko'rinishida):",
            "skills": "⚡️ Qo'shimcha ko'nikmalaringiz bor? (Masalan: Kompyuter, haydovchilik):"
        }

        text = questions.get(current_req, f"Iltimos, {current_req} ma'lumotini yuboring:")

        kb = InlineKeyboardBuilder()
        if step > 0:
            kb.row(types.InlineKeyboardButton(
                text="⬅️ Oldingi savolga qaytish",
                callback_data="back_step"
            ))
        else:
            kb.row(types.InlineKeyboardButton(
                text="❌ Bekor qilish",
                callback_data="find_job"
            ))

        await message.answer(text, reply_markup=kb.as_markup())
    else:
        await finalize_application(message, state)


# =====================================================
# 6-QISM: OLDINGI QADAMGA QAYTISH (BACK STEP)
# =====================================================

@router.callback_query(JobSeeker.filling_form, F.data == "back_step")
async def process_back_step(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_step = data.get("current_step", 0)

    if current_step > 0:
        new_step = current_step - 1
        await state.update_data(current_step=new_step)

        answers = data.get("answers", {})
        reqs = data.get("all_reqs", [])
        req_key = reqs[new_step].strip()
        if req_key in answers:
            del answers[req_key]
        await state.update_data(answers=answers)

        try:
            await callback.message.delete()
        except Exception:
            pass
        await ask_next_step(callback.message, state)
    await callback.answer()


# =====================================================
# 7-QISM: JAVOBLARNI QABUL QILISH
# =====================================================

@router.message(JobSeeker.filling_form)
async def handle_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    reqs = data['all_reqs']
    step = data['current_step']
    answers = data.get('answers', {})
    current_req = reqs[step].strip()

    # Media tekshiruvi va saqlash
    if current_req == "photo":
        if not message.photo:
            return await message.answer("🖼 Iltimos, rasm yuboring!")
        answers["photo"] = message.photo[-1].file_id

    elif current_req == "voice":
        if not message.voice:
            return await message.answer("🎤 Iltimos, ovozli xabar yuboring!")
        answers["voice"] = message.voice.file_id

    elif message.contact:
        answers[current_req] = message.contact.phone_number
    else:
        answers[current_req] = message.text

    await state.update_data(answers=answers, current_step=step + 1)
    await ask_next_step(message, state)


# =====================================================
# 8-QISM: YAKUNIY KO'RISH VA TASDIQLASH
# =====================================================

async def finalize_application(message: types.Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", {})
    direction = data.get("direction", "Noma'lum")

    summary_text = f"📋 <b>Sizning anketangiz:</b>\n"
    summary_text += f"━━━━━━━━━━━━━━━━━━━━\n"
    summary_text += f"📍 <b>Yo'nalish:</b> {direction}\n\n"

    pretty_names = {
        "full_name": "👤 Ism:",
        "age": "🔢 Yosh:",
        "phone": "📞 Tel:",
        "experience": "⏳ Tajriba:",
        "address": "📍 Manzil:",
        "languages": "🌐 Tillar:",
        "education": "🎓 Ma'lumot:",
        "expected_salary": "💰 Kutilayotgan maosh:",
        "portfolio": "📁 Portfolio:",
        "skills": "⚡️ Ko'nikmalar:",
        "voice": "🎤 Ovozli xabar:",
        "photo": "🖼 Rasm:"
    }

    for key, value in answers.items():
        if key not in ["photo", "voice"]:
            name = pretty_names.get(key, key.capitalize())
            summary_text += f"<b>{name}</b> {value}\n"
        elif key == "voice":
            summary_text += f"<b>🎤 Ovozli xabar:</b> ✅ Yuborildi\n"
        elif key == "photo":
            summary_text += f"<b>🖼 Rasm:</b> ✅ Yuklandi\n"

    summary_text += f"━━━━━━━━━━━━━━━━━━━━\n"
    summary_text += f"⚠️ Ma'lumotlar to'g'rimi? Tasdiqlasangiz, ish beruvchiga yuboriladi."

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(
        text="✅ Tasdiqlash va Yuborish",
        callback_data="send_to_employer"
    ))
    kb.row(types.InlineKeyboardButton(
        text="⬅️ Tahrirlash (Orqaga)",
        callback_data="back_step"
    ))
    kb.row(types.InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="find_job"
    ))
    kb.adjust(1)

    photo_id = answers.get("photo")

    if photo_id:
        await message.answer_photo(
            photo=photo_id,
            caption=summary_text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            summary_text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )


# =====================================================
# 9-QISM: ISH BERUVCHIGA YUBORISH
# =====================================================

@router.callback_query(F.data == "send_to_employer")
async def send_to_employer(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()

    owner_id = data.get('target_owner')
    direction = data.get('direction', "Ko'rsatilmagan")
    answers = data.get('answers', {})

    if not owner_id:
        return await callback.answer(
            "❌ Xatolik: Ish beruvchi ma'lumotlari topilmadi. Qaytadan urinib ko'ring.",
            show_alert=True
        )

    candidate_id = callback.from_user.id
    candidate_name = callback.from_user.full_name

    summary = (
        f"📥 <b>YANGI ARIZA KELDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>Yo'nalish:</b> {direction}\n"
        f"👤 <b>Nomzod:</b> <a href='tg://user?id={candidate_id}'>"
        f"{candidate_name}</a>\n"
        f"🆔 <b>ID:</b> <code>{candidate_id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )

    pretty_names = {
        "full_name": "👤 Ism", "age": "🔢 Yosh",
        "phone": "📞 Tel", "experience": "⏳ Tajriba",
        "address": "📍 Manzil", "languages": "🌐 Tillar",
        "education": "🎓 Ma'lumot", "expected_salary": "💰 Maosh",
        "portfolio": "📁 Portfolio", "skills": "⚡️ Ko'nikmalar"
    }

    for req, val in answers.items():
        if req not in ['photo', 'voice']:
            label = pretty_names.get(req, req.capitalize())
            summary += f"🔹 <b>{label}:</b> {val}\n"

    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(
            text="✅ Bog'lanish",
            callback_data=f"contact_{candidate_id}"
        ),
        types.InlineKeyboardButton(
            text="⭐ Saqlash",
            callback_data=f"fav_{candidate_id}"
        )
    )
    kb.row(types.InlineKeyboardButton(
        text="❌ Rad etish",
        callback_data=f"rej_cand_{candidate_id}"
    ))
    kb.adjust(2, 1)

    try:
        if 'photo' in answers:
            await bot.send_photo(
                owner_id,
                answers['photo'],
                caption=summary,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                owner_id,
                summary,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )

        if 'voice' in answers:
            await bot.send_voice(
                owner_id,
                answers['voice'],
                caption=f"🎤 {candidate_name}ning ovozli tanishtiruvi"
            )

    except Exception as e:
        logging.error(f"Tadbirkorga yuborishda xato: {e}")
        return await callback.answer(
            "❌ Arizani yuborib bo'lmadi (Ish beruvchi botni bloklagan bo'lishi mumkin).",
            show_alert=True
        )

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "🚀 <b>Arizangiz muvaffaqiyatli yuborildi!</b>\n\n"
        "Tadbirkor ma'lumotlaringizni ko'rib chiqib, o'zi siz bilan bog'lanadi.",
        parse_mode="HTML"
    )

    await state.clear()


# =====================================================
# 10-QISM: NOMZOD SOZLAMALARI
# =====================================================

@router.callback_query(F.data == "cand_settings")
async def candidate_settings(callback: types.CallbackQuery, db_pool):
    user_id = callback.from_user.id

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT notifications FROM users WHERE user_id = $1", user_id
        )

    is_enabled = (
        user['notifications']
        if user and user['notifications'] is not None
        else True
    )

    text = (
        "⚙️ <b>Sozlamalar bo'limi</b>\n\n"
        "Bu yerda siz profilingizni boshqarishingiz, yangi ishlar haqidagi "
        "bildirishnomalarni sozlashingiz yoki ma'lumotlaringizni o'chirishingiz mumkin."
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=candidate_settings_keyboard(is_enabled),
        parse_mode="HTML"
    )


# =====================================================
# 11-QISM: NOMZOD PANELIGA QAYTISH
# =====================================================

@router.callback_query(F.data == "candidate_panel")
async def back_to_cand_panel(callback: types.CallbackQuery, state: FSMContext):
    # State'ni tozalaymiz (qayerdan qaytishidan qat'iy nazar)
    await state.clear()

    await callback.message.edit_text(
        "👋 <b>Nomzod paneli</b>\n\nQuyidagi menyu orqali davom eting:",
        reply_markup=candidate_panel_keyboard(),
        parse_mode="HTML"
    )


# =====================================================
# 12-QISM: PROFIL YARATISH
# =====================================================

CATEGORIES = ["Sotuvchi", "Haydovchi", "Admin", "Dasturchi", "Oshpaz", "Menejer"]


@router.callback_query(F.data == "create_profile")
async def start_profile(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "👋 <b>Profilingizni yaratishni boshlaymiz!</b>\n\n"
        "Ism va familiyangizni kiriting:",
        parse_mode="HTML"
    )
    await state.set_state(CandidateProfile.waiting_name)


@router.message(CandidateProfile.waiting_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("🔢 Yoshingizni kiriting (raqamda):")
    await state.set_state(CandidateProfile.waiting_age)


@router.message(CandidateProfile.waiting_age)
async def process_age(message: types.Message, state: FSMContext):
    await state.update_data(age=message.text)

    kb = InlineKeyboardBuilder()
    for cat in CATEGORIES:
        kb.button(text=cat, callback_data=f"set_cat_{cat}")
    kb.row(types.InlineKeyboardButton(
        text="✍️ Boshqa yo'nalish",
        callback_data="other_category"
    ))
    kb.adjust(2)

    await message.answer(
        "🎯 <b>Ish yo'nalishingizni tanlang:</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(CandidateProfile.waiting_category)


@router.callback_query(CandidateProfile.waiting_category, F.data.startswith("set_cat_"))
async def process_category_callback(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.replace("set_cat_", "")
    await state.update_data(category=category)
    await callback.message.edit_text(
        f"✅ Tanlandi: <b>{category}</b>\n\n"
        "⏳ Ish tajribangiz haqida yozing:",
        parse_mode="HTML"
    )
    await state.set_state(CandidateProfile.waiting_experience)


@router.callback_query(CandidateProfile.waiting_category, F.data == "other_category")
async def other_category_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 <b>O'z yo'nalishingizni yozib yuboring:</b>",
        parse_mode="HTML"
    )
    await state.set_state(CandidateProfile.waiting_custom_category)


@router.message(CandidateProfile.waiting_custom_category)
async def process_custom_category(message: types.Message, state: FSMContext):
    category = message.text
    await state.update_data(category=category)
    await message.answer(
        f"✅ Qabul qilindi: <b>{category}</b>\n\n"
        "⏳ Ish tajribangiz haqida yozing:",
        parse_mode="HTML"
    )
    await state.set_state(CandidateProfile.waiting_experience)


@router.message(CandidateProfile.waiting_experience)
async def process_exp(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await message.answer("📸 O'zingizni rasmingizni yuboring (yoki biron-bir rasm):")
    await state.set_state(CandidateProfile.waiting_photo)


@router.message(CandidateProfile.waiting_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer(
        "🎤 <b>Oxirgi qadam!</b> O'zingiz haqida qisqacha ovozli xabar (voice) yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(CandidateProfile.waiting_voice)


@router.message(CandidateProfile.waiting_voice, F.voice)
async def finalize_profile(message: types.Message, state: FSMContext, db_pool):
    data = await state.get_data()
    user_id = message.from_user.id

    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE users SET
                full_name = $1, age = $2, category = $3,
                experience = $4, photo_id = $5, voice_id = $6
            WHERE user_id = $7
        """, data['full_name'], int(data['age']), data['category'],
             data['experience'], data['photo_id'], message.voice.file_id, user_id)

    await message.answer(
        "🎉 <b>Profilingiz muvaffaqiyatli saqlandi!</b>\n"
        "Endi sizga mos ishlar chiqsa, bot sizga xabar beradi.",
        parse_mode="HTML"
    )
    await state.clear()


# =====================================================
# 13-QISM: BILDIRISHNOMALARNI YOQISH/O'CHIRISH
# =====================================================

@router.callback_query(F.data == "toggle_cand_notif")
async def toggle_candidate_notifications(callback: types.CallbackQuery, db_pool):
    user_id = callback.from_user.id

    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE users
            SET notifications = NOT COALESCE(notifications, TRUE)
            WHERE user_id = $1
        """, user_id)

        new_status = await conn.fetchval(
            "SELECT notifications FROM users WHERE user_id = $1", user_id
        )

    status_text = "yoqildi ✅" if new_status else "o'chirildi ❌"
    await callback.answer(f"Bildirishnomalar {status_text}")

    await callback.message.edit_reply_markup(
        reply_markup=candidate_settings_keyboard(notifications_enabled=new_status)
    )


# =====================================================
# 14-QISM: PROFILNI O'CHIRISH (2 BOSQICHLI)
# =====================================================

@router.callback_query(F.data == "delete_my_profile")
async def ask_delete_confirmation(callback: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(
            text="✅ Ha, o'chirilsin",
            callback_data="confirm_delete_profile"
        ),
        types.InlineKeyboardButton(
            text="❌ Yo'q, qolsin",
            callback_data="cand_settings"
        )
    )

    await callback.message.edit_text(
        "⚠️ <b>Diqqat!</b>\n\n"
        "Profilingizni o'chirsangiz, barcha ma'lumotlaringiz o'chib ketadi "
        "va yangi ishlar haqida bildirishnomalar kelmaydi. "
        "Haqiqatan ham o'chirmoqchimisiz?",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "confirm_delete_profile")
async def confirm_delete_profile(callback: types.CallbackQuery, db_pool):
    user_id = callback.from_user.id

    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE users SET
                role = NULL,
                category = NULL,
                age = NULL,
                experience = NULL,
                photo_id = NULL,
                voice_id = NULL,
                notifications = FALSE
            WHERE user_id = $1
        """, user_id)

    await callback.message.edit_text(
        "🗑 <b>Profilingiz muvaffaqiyatli o'chirildi.</b>\n\n"
        "Botdan qayta foydalanish uchun /start bosing.",
        parse_mode="HTML"
    )
    await callback.answer("Profil o'chirildi")


# =====================================================
# 15-QISM: MENING ANKETAM (REZYUME KO'RISH)
# =====================================================

@router.callback_query(F.data == "my_resume")
async def show_my_resume_with_media(callback: types.CallbackQuery, db_pool):
    async with db_pool.acquire() as conn:
        user_data = await conn.fetchrow(
            "SELECT info_json FROM resumes WHERE user_id = $1",
            callback.from_user.id
        )

    if not user_data:
        return await callback.answer(
            "Sizda hali saqlangan anketa yo'q!", show_alert=True
        )

    data = json.loads(user_data['info_json'])

    summary = "👤 <b>Sizning ma'lumotlaringiz:</b>\n\n"
    pretty_names = {
        "full_name": "Ism", "age": "Yosh",
        "phone": "Tel", "experience": "Tajriba"
    }

    for key, val in data.items():
        if key not in ['photo', 'voice']:
            summary += f"<b>{pretty_names.get(key, key)}:</b> {val}\n"

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(
        text="⬅️ Orqaga",
        callback_data="candidate_panel"
    ))

    if 'photo' in data:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo=data['photo'],
            caption=summary,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            summary,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
