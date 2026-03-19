import os
import json
import random
import asyncio
from datetime import datetime

from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import LabeledPrice, PreCheckoutQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from states.states import AdCreation, ContactState
from keyboards.inlines import (
    admin_panel_keyboard,
    candidate_panel_keyboard,
    get_fav_keyboard,
    room_types_keyboard,
    payment_type_keyboard,
    employer_panel_keyboard,
    sectors_keyboard,
    requirements_keyboard,
    regions_keyboard
)

router = Router()  # <<<--- FAQAT 1 TA ROUTER!


# =====================================================
# 1-QISM: YORDAMCHI FUNKSIYALAR
# =====================================================

def get_number_by_plan(plan):
    plan = plan.lower()
    if plan == "gold":
        gold_list = [f"{i}" * 4 for i in range(10)]
        return random.choice(gold_list)
    elif plan == "silver":
        a = random.randint(0, 9)
        b = random.randint(0, 9)
        while a == b:
            b = random.randint(0, 9)
        patterns = [
            f"{a}{a}{b}{b}",
            f"777{a}",
            f"{a}777",
            f"{a}{b}{b}{b}",
            f"{b}{b}{b}{a}"
        ]
        return random.choice(patterns)
    elif plan == "titan":
        return f"{random.randint(0, 9999):04d}"
    else:
        return f"{random.randint(0, 9999):04d}"


# =====================================================
# 2-QISM: TO'LOV TIZIMI (XONA SOTIB OLISH)
# =====================================================

@router.callback_query(F.data.startswith("buy_room_"))
async def select_room_plan(callback: types.CallbackQuery, state: FSMContext):
    plan = callback.data.split("_")[2]
    await state.update_data(selected_plan=plan)

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(
        text="✅ Davom etish", callback_data="pay_click_1"
    ))
    kb.row(types.InlineKeyboardButton(
        text="⬅️ Orqaga", callback_data="buy_room_menu"
    ))

    await callback.message.edit_text(
        f"Siz <b>{plan.upper()}</b> tarifini tanladingiz.\n"
        f"{'Bu tarif mutlaqo bepul!' if plan == 'standard' else 'Davom etish uchun to\'lovni amalga oshiring.'}",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "pay_click_1")
async def process_click_pay(callback: types.CallbackQuery, bot: Bot,
                             state: FSMContext, db_pool):
    data = await state.get_data()
    plan = data.get("selected_plan", "standard").lower()

    # STANDARD — BEPUL XONA
    if plan == "standard":
        user_id = callback.from_user.id

        async with db_pool.acquire() as conn:
            while True:
                num = get_number_by_plan("standard")
                exists = await conn.fetchval(
                    "SELECT 1 FROM rooms WHERE room_number = $1", num
                )
                if not exists:
                    break

            await conn.execute(
                "INSERT INTO rooms (room_number, room_type, owner_id, is_sold) "
                "VALUES ($1, $2, $3, TRUE)",
                num, "standard", user_id
            )
            await conn.execute(
                "UPDATE users SET role = 'employer' WHERE user_id = $1",
                user_id
            )

        await callback.message.edit_text(
            f"🎁 **Tabriklaymiz!**\n\n"
            f"Sizga Standard tarif bo'yicha bepul xona berildi!\n"
            f"Xona raqamingiz: 🔥 `{num}` 🔥\n\n"
            f"Endi /panel orqali ishni boshlashingiz mumkin!",
            parse_mode="Markdown"
        )
        await state.clear()
        return

    # PULLIK TARIFLAR (SILVER, GOLD)
    prices_map = {"silver": 150000, "gold": 500000}
    amount = prices_map.get(plan)

    if not amount:
        return await callback.answer("Noma'lum tarif!")

    await callback.message.delete()
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{plan.upper()} Xona",
        description=f"Korgoh: {plan} darajali pullik raqam",
        payload=f"pay_room_{plan}",
        provider_token=os.getenv("CLICK_TOKEN"),
        currency="UZS",
        prices=[LabeledPrice(
            label=f"{plan.capitalize()} xona", amount=amount * 100
        )]
    )


# =====================================================
# 3-QISM: PRE-CHECKOUT VA TO'LOV TASDIQLASH
# =====================================================

@router.pre_checkout_query()
async def checkout_handler(pre_checkout: PreCheckoutQuery):
    await pre_checkout.answer(ok=True)


@router.message(F.successful_payment)
async def unified_payment_handler(message: types.Message, db_pool, bot: Bot):
    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id

    try:
        # BALL SOTIB OLISH
        if "refill_ball" in payload:
            ball_added = int(payload.split("_")[-1])

            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET balance = COALESCE(balance, 0) + $1 "
                    "WHERE user_id = $2",
                    ball_added, user_id
                )
                room = await conn.fetchrow(
                    "SELECT room_number FROM rooms WHERE owner_id = $1",
                    user_id
                )

            await message.answer(f"✅ Balans to'ldirildi: +{ball_added} ball")
            if room:
                return await message.answer(
                    "Panelga qaytish:",
                    reply_markup=employer_panel_keyboard(room['room_number'])
                )

        # XONA SOTIB OLISH
        elif "buy_room" in payload or "pay_" in payload:
            plan = payload.split("_")[-1]

            async with db_pool.acquire() as conn:
                num = get_number_by_plan(plan)
                await conn.execute(
                    "UPDATE users SET role = 'employer' WHERE user_id = $1",
                    user_id
                )
                await conn.execute(
                    "DELETE FROM rooms WHERE owner_id = $1", user_id
                )
                await conn.execute(
                    "INSERT INTO rooms (room_number, room_type, owner_id, is_sold) "
                    "VALUES ($1, $2, $3, TRUE)",
                    num, plan, user_id
                )

            await message.answer(
                f"🎊 Tabriklaymiz! To'lov muvaffaqiyatli!\n"
                f"🏢 Sizning xonangiz: <b>{num}</b>",
                reply_markup=employer_panel_keyboard(num),
                parse_mode="HTML"
            )
            return await bot.send_message(
                os.getenv("ADMIN_ID"), f"💰 Xona sotildi: {num}"
            )

    except Exception as e:
        print(f"XATOLIK YUZ BERDI: {e}")
        await message.answer(
            "⚠️ To'lov qabul qilindi, lekin ma'lumotlarni yangilashda "
            "xato chiqdi. Admin bilan bog'laning."
        )


# =====================================================
# 4-QISM: PANEL KOMANDASI
# =====================================================

@router.message(Command("panel"))
async def show_panel(message: types.Message, db_pool):
    user_id = message.from_user.id

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT users.role, rooms.room_number
            FROM users
            LEFT JOIN rooms ON users.user_id = rooms.owner_id
            WHERE users.user_id = $1
            ORDER BY rooms.id DESC LIMIT 1
        """, user_id)

    if not user:
        return await message.answer("Avval ro'yxatdan o'ting! /start")

    if user['role'] == 'employer':
        room_num = user['room_number'] or "Mavjud emas"
        await message.answer(
            f"🏢 **Tadbirkor paneli**\nXona raqamingiz: `{room_num}`",
            reply_markup=employer_panel_keyboard(room_num),
            parse_mode="Markdown"
        )
    elif user['role'] == 'candidate':
        await message.answer(
            "🔍 **Nomzod paneli**",
            reply_markup=candidate_panel_keyboard()
        )

    if str(user_id) == os.getenv("ADMIN_ID"):
        await message.answer(
            "👑 **Admin paneli**", reply_markup=admin_panel_keyboard()
        )


@router.callback_query(F.data == "employer_panel")
async def back_to_employer_panel(callback: types.CallbackQuery, db_pool):
    user_id = callback.from_user.id

    async with db_pool.acquire() as conn:
        room_data = await conn.fetchval(
            "SELECT room_number FROM rooms WHERE owner_id = $1 LIMIT 1",
            user_id
        )

    room_number = room_data if room_data else "Yo'q"

    await callback.message.edit_text(
        f"🏠 <b>Tadbirkorlik paneliga xush kelibsiz!</b>\n"
        f"Xonangiz: №{room_number}",
        reply_markup=employer_panel_keyboard(room_number),
        parse_mode="HTML"
    )
    await callback.answer()


# =====================================================
# 5-QISM: E'LON YARATISH
# =====================================================

@router.callback_query(F.data == "new_ad")
async def start_ad(callback: types.CallbackQuery, state: FSMContext, db_pool):
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        balance = await conn.fetchval(
            "SELECT balance FROM users WHERE user_id = $1", user_id
        )

    if (balance or 0) < 10:
        return await callback.answer(
            "⚠️ Balans yetarli emas (10 ball kerak)!", show_alert=True
        )

    await state.set_state(AdCreation.sector)
    await callback.message.edit_text(
        "📝 <b>Sohani tanlang:</b>",
        reply_markup=sectors_keyboard(), parse_mode="HTML"
    )


@router.callback_query(AdCreation.sector, F.data.startswith("setsector_"))
async def process_sector(callback: types.CallbackQuery, state: FSMContext):
    sector_name = callback.data.split("_")[1]
    await state.update_data(chosen_sector=sector_name)
    await state.set_state(AdCreation.custom_service)
    await callback.message.edit_text(
        f"✅ Soha: <b>{sector_name}</b>\n"
        f"📝 Yo'nalishni yozing (masalan: Backend Developer):",
        parse_mode="HTML"
    )


@router.message(AdCreation.custom_service)
async def get_custom_service(message: types.Message, state: FSMContext):
    await state.update_data(chosen_sub=message.text, selected_reqs=[])
    await state.set_state(AdCreation.requirements)
    await message.answer(
        "📋 Nomzoddan nimalarni talab qilasiz?",
        reply_markup=requirements_keyboard([]),
        parse_mode="HTML"
    )


@router.callback_query(AdCreation.requirements, F.data.startswith("req_"))
async def toggle_req(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    reqs = data.get("selected_reqs", [])
    current = callback.data.replace("req_", "")
    if current in reqs:
        reqs.remove(current)
    else:
        reqs.append(current)
    await state.update_data(selected_reqs=reqs)
    await callback.message.edit_reply_markup(
        reply_markup=requirements_keyboard(reqs)
    )
    await callback.answer()


@router.callback_query(AdCreation.requirements, F.data == "finish_ad")
async def ask_region(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdCreation.region)
    await callback.message.edit_text(
        "📍 <b>Ish qaysi hududda? (Viloyatni tanlang):</b>",
        reply_markup=regions_keyboard(), parse_mode="HTML"
    )


@router.callback_query(AdCreation.region, F.data.startswith("reg_"))
async def process_region(callback: types.CallbackQuery, state: FSMContext):
    region = callback.data.split("_")[1]
    await state.update_data(chosen_region=region)
    await state.set_state(AdCreation.job_type)

    kb = InlineKeyboardBuilder()
    kb.button(text="🏠 Online", callback_data="type_Online")
    kb.button(text="🏢 Offline", callback_data="type_Offline")
    await callback.message.edit_text(
        f"📍 Hudud: {region}\n💻 <b>Ish turini tanlang:</b>",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )


@router.callback_query(AdCreation.job_type, F.data.startswith("type_"))
async def process_job_type(callback: types.CallbackQuery, state: FSMContext):
    j_type = callback.data.split("_")[1]
    await state.update_data(chosen_job_type=j_type)
    await state.set_state(AdCreation.salary)
    await callback.message.edit_text(
        "💰 <b>Ish haqqini yozing:</b>\n(Masalan: 500$ yoki Kelishiladi)",
        parse_mode="HTML"
    )


@router.message(AdCreation.salary)
async def process_salary(message: types.Message, state: FSMContext):
    await state.update_data(chosen_salary=message.text)
    await state.set_state(AdCreation.work_time)
    await message.answer(
        "⏰ <b>Ish vaqtini yozing:</b>\n(Masalan: 09:00 - 18:00)",
        parse_mode="HTML"
    )


@router.message(AdCreation.work_time)
async def preview_ad(message: types.Message, state: FSMContext):
    await state.update_data(chosen_work_time=message.text)
    data = await state.get_data()

    sector = data.get("chosen_sector")
    sub = data.get("chosen_sub")
    region = data.get("chosen_region")
    j_type = data.get("chosen_job_type")
    salary = data.get("chosen_salary")
    work_time = message.text
    reqs = ", ".join([
        r.replace("_", " ").capitalize()
        for r in data.get("selected_reqs", [])
    ])

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
    await message.answer(
        preview_text, reply_markup=kb.as_markup(), parse_mode="HTML"
    )


@router.callback_query(AdCreation.confirm, F.data == "confirm_ad_final")
async def send_to_admin_final(callback: types.CallbackQuery, state: FSMContext,
                                bot: Bot, db_pool):
    data = await state.get_data()
    user = callback.from_user

    async with db_pool.acquire() as conn:
        ad_id = await conn.fetchval("""
            INSERT INTO ads (owner_id, soha, sub_sector, region,
                             job_type, salary, work_time,
                             selected_reqs, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
            RETURNING id
        """, user.id, data['chosen_sector'], data['chosen_sub'],
             data['chosen_region'], data['chosen_job_type'],
             data['chosen_salary'], data['chosen_work_time'],
             ",".join(data['selected_reqs']))

    reqs_list = ", ".join([
        r.replace("_", " ").capitalize()
        for r in data['selected_reqs']
    ])
    admin_text = (
        f"🚀 <b>YANGI E'LON (#ID_{ad_id})</b>\n\n"
        f"👤 <b>Tadbirkor:</b> {user.full_name} "
        f"(<a href='tg://user?id={user.id}'>Profil</a>)\n"
        f"🏢 <b>Soha:</b> {data['chosen_sector']}\n"
        f"🎯 <b>Yo'nalish:</b> {data['chosen_sub']}\n"
        f"📍 <b>Hudud:</b> {data['chosen_region']} "
        f"({data['chosen_job_type']})\n"
        f"💰 <b>Maosh:</b> {data['chosen_salary']}\n"
        f"⏰ <b>Ish vaqti:</b> {data['chosen_work_time']}\n"
        f"📋 <b>Talablar:</b> {reqs_list}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(
        text="✅ Tasdiqlash (Kanalga)",
        callback_data=f"approve_{user.id}"
    )
    kb.button(
        text="❌ Rad etish (Sabab bilan)",
        callback_data=f"reject_ask_{ad_id}_{user.id}"
    )
    kb.adjust(1)

    await bot.send_message(
        os.getenv("ADMIN_ID"), admin_text,
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )
    await callback.message.edit_text(
        "🚀 <b>Rahmat! E'loningiz adminga yuborildi.</b>",
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(AdCreation.confirm, F.data == "cancel_ad_final")
async def cancel_ad(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>E'lon bekor qilindi.</b>", parse_mode="HTML"
    )


# =====================================================
# 6-QISM: RAD ETISH (ADMIN)
# =====================================================

@router.callback_query(F.data.startswith("reject_ask_"))
async def ask_reject_reason(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    ad_id = parts[2]
    user_id = parts[3]

    await state.set_state(AdCreation.reject_reason)
    await state.update_data(reject_ad_id=ad_id, reject_user_id=user_id)

    await callback.message.answer(
        f"⚠️ <b>ID {ad_id} uchun rad etish sababini yozing:</b>\n"
        f"(Tadbirkorga aynan shu matn boradi)",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdCreation.reject_reason)
async def process_reject_reason(message: types.Message, state: FSMContext,
                                  bot: Bot, db_pool):
    if message.from_user.id != int(os.getenv("ADMIN_ID")):
        return

    data = await state.get_data()
    ad_id = int(data['reject_ad_id'])
    user_id = int(data['reject_user_id'])
    reason = message.text

    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE ads SET status = 'rejected' WHERE id = $1", ad_id
        )

    try:
        await bot.send_message(
            user_id,
            f"❌ <b>Sizning e'loningiz rad etildi.</b>\n\n"
            f"📝 <b>Sabab:</b> {reason}\n\n"
            f"<i>Iltimos, xatolarni to'g'rilab qaytadan urinib ko'ring.</i>",
            parse_mode="HTML"
        )
        await message.answer("✅ Sabab tadbirkorga yuborildi.")
    except Exception:
        await message.answer(
            "⚠️ Tadbirkorga xabar yuborib bo'lmadi "
            "(bloklagan bo'lishi mumkin)."
        )

    await state.clear()


# =====================================================
# 7-QISM: NOMZODLARNI BOSHQARISH (Contact, Reject)
# =====================================================

@router.callback_query(F.data.startswith("rej_cand_"))
async def reject_candidate(callback: types.CallbackQuery, bot: Bot):
    candidate_id = int(callback.data.split("_")[2])

    try:
        if callback.message.caption:
            await callback.message.edit_caption(
                caption=callback.message.caption +
                        "\n\n❌ <b>Ushbu nomzod rad etildi.</b>",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                callback.message.text +
                "\n\n❌ <b>Ushbu nomzod rad etildi.</b>",
                parse_mode="HTML"
            )
    except Exception:
        pass

    try:
        await bot.send_message(
            candidate_id,
            "😔 Kechirasiz, arizangiz ko'rib chiqildi va "
            "ish beruvchi tomonidan rad etildi."
        )
    except Exception:
        pass

    await callback.answer("Nomzod rad etildi.", show_alert=False)


@router.callback_query(F.data.startswith("contact_"))
async def start_contact(callback: types.CallbackQuery, state: FSMContext):
    candidate_id = int(callback.data.split("_")[1])
    await state.update_data(candidate_id=candidate_id)

    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(
            text="🎤 Ovozli (Golos)", callback_data="type_voice"
        ),
        types.InlineKeyboardButton(
            text="📝 Xabar (Uchrashuv)", callback_data="type_text"
        )
    )

    await callback.message.answer(
        "Ishchi bilan qanday bog'lanamiz?",
        reply_markup=kb.as_markup()
    )
    await state.set_state(ContactState.choosing_method)
    await callback.answer()


@router.callback_query(ContactState.choosing_method, F.data == "type_voice")
async def ask_voice(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🎤 Ishchi uchun ovozli xabaringizni yuboring:"
    )
    await state.set_state(ContactState.waiting_voice)


@router.message(ContactState.waiting_voice, F.voice)
async def send_voice_to_candidate(message: types.Message, state: FSMContext,
                                    bot: Bot):
    data = await state.get_data()
    await bot.send_message(
        data['candidate_id'],
        "📢 <b>Sizga ish beruvchidan ovozli xabar keldi:</b>",
        parse_mode="HTML"
    )
    await bot.send_voice(data['candidate_id'], message.voice.file_id)
    await message.answer("✅ Ovozli xabaringiz yuborildi!")
    await state.clear()


@router.callback_query(ContactState.choosing_method, F.data == "type_text")
async def ask_details(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📅 Uchrashuv sanasi va telefon raqamingizni yozing:\n"
        "<i>Masalan: Ertaga soat 10:00 da, +998901234567</i>",
        parse_mode="HTML"
    )
    await state.set_state(ContactState.waiting_details)


@router.message(ContactState.waiting_details)
async def ask_location(message: types.Message, state: FSMContext):
    await state.update_data(meeting_info=message.text)

    kb = ReplyKeyboardBuilder()
    kb.button(text="📍 Lokatsiya yuborish", request_location=True)

    await message.answer(
        "📍 Endi uchrashuv joyi (lokatsiya)ni yuboring:",
        reply_markup=kb.as_markup(
            resize_keyboard=True, one_time_keyboard=True
        )
    )
    await state.set_state(ContactState.waiting_location)


@router.message(ContactState.waiting_location, F.location)
async def finalize_contact(message: types.Message, state: FSMContext,
                            bot: Bot):
    data = await state.get_data()
    candidate_id = data['candidate_id']
    info = data['meeting_info']

    text_to_cand = (
        "🎉 <b>Sizni uchrashuvga taklif qilishdi!</b>\n\n"
        f"📝 <b>Ma'lumot:</b> {info}\n"
        "📍 <b>Manzil:</b> Pastdagi lokatsiya bo'yicha kelishingiz mumkin."
    )

    await bot.send_message(candidate_id, text_to_cand, parse_mode="HTML")
    await bot.send_location(
        candidate_id,
        message.location.latitude,
        message.location.longitude
    )
    await message.answer(
        "✅ Ma'lumotlar ishchiga yuborildi!",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.clear()


# =====================================================
# 8-QISM: SAQLANGAN NOMZODLAR (FAVORITES) — TUZATILDI!
# =====================================================
# ❌ ESKI MUAMMO:
#   1) fav_ prefiksi fav_page_ ni ham ushlab olardi
#   2) info_json ustuni bazada yo'q edi
#   3) State bo'sh qaytardi
#
# ✅ TUZATILDI:
#   1) savefav_ prefiksi ishlatilmoqda (fav_page_ bilan conflict yo'q)
#   2) info_json bo'lmasa xabar matnidan parsing qilinadi
#   3) State o'rniga xabar matnidan ma'lumot olinadi

@router.callback_query(F.data.startswith("savefav_"))
async def save_to_favorites(callback: types.CallbackQuery, db_pool):
    """Nomzodni saqlanganlarga qo'shish"""
    # 1. Candidate ID ni olish: savefav_12345678
    try:
        candidate_id = int(callback.data.replace("savefav_", ""))
    except (IndexError, ValueError):
        return await callback.answer("❌ ID xatosi", show_alert=True)

    owner_id = callback.from_user.id

    # 2. Xabar matnidan ma'lumotlarni ajratib olish
    # (State ishlamasligi mumkin — chunki bu TADBIRKOR ekrani)
    answers = {}
    msg_text = (
        callback.message.caption
        if callback.message.caption
        else callback.message.text
    )

    if msg_text:
        lines = msg_text.split('\n')
        for line in lines:
            if "Ism" in line and ":" in line:
                answers['full_name'] = line.split(":", 1)[1].strip()
            elif "Yosh" in line and ":" in line:
                answers['age'] = line.split(":", 1)[1].strip()
            elif "Tel" in line and ":" in line:
                answers['phone'] = line.split(":", 1)[1].strip()
            elif "Tajriba" in line and ":" in line:
                answers['experience'] = line.split(":", 1)[1].strip()
            elif "Manzil" in line and ":" in line:
                answers['address'] = line.split(":", 1)[1].strip()
            elif "Yo'nalish" in line and ":" in line:
                answers['direction'] = line.split(":", 1)[1].strip()

    # Rasm ID sini olish
    if callback.message.photo:
        answers['photo'] = callback.message.photo[-1].file_id

    info_json = json.dumps(answers, ensure_ascii=False)

    # 3. Bazaga yozish (info_json bor-yo'qligini tekshiradi)
    async with db_pool.acquire() as conn:
        # Avval jadval tuzilmasini tekshiramiz
        has_info_col = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'favorites' 
                AND column_name = 'info_json'
            )
        """)

        # Mavjudligini tekshirish
        exists = await conn.fetchval(
            "SELECT id FROM favorites "
            "WHERE owner_id = $1 AND candidate_id = $2",
            owner_id, candidate_id
        )

        if not exists:
            if has_info_col:
                await conn.execute(
                    "INSERT INTO favorites "
                    "(owner_id, candidate_id, info_json) "
                    "VALUES ($1, $2, $3)",
                    owner_id, candidate_id, info_json
                )
            else:
                await conn.execute(
                    "INSERT INTO favorites "
                    "(owner_id, candidate_id) "
                    "VALUES ($1, $2)",
                    owner_id, candidate_id
                )
            text = "⭐ Nomzod saralanganlarga saqlandi!"
        else:
            text = "⚠️ Bu nomzod allaqachon ro'yxatingizda bor."

    await callback.answer(text, show_alert=True)

    # 4. Tugmani yangilash
    try:
        current_kb = callback.message.reply_markup.inline_keyboard
        new_kb_list = []
        for row in current_kb:
            new_row = []
            for button in row:
                if button.callback_data == callback.data:
                    new_row.append(
                        types.InlineKeyboardButton(
                            text="⭐ Saqlandi ✅",
                            callback_data="none"
                        )
                    )
                else:
                    new_row.append(button)
            new_kb_list.append(new_row)

        await callback.message.edit_reply_markup(
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=new_kb_list
            )
        )
    except Exception:
        pass


# --- SAQLANGANLARNI KO'RISH (PAGINATION) ---

@router.callback_query(F.data == "view_favorites")
async def view_favorites_start(callback: types.CallbackQuery,
                                db_pool, bot: Bot):
    """Birinchi sahifani ko'rsatish"""
    await show_favorites_paged(callback, db_pool, bot, page=0)


@router.callback_query(F.data.startswith("fav_page_"))
async def view_favorites_page(callback: types.CallbackQuery,
                               db_pool, bot: Bot):
    """Tanlangan sahifani ko'rsatish"""
    try:
        page = int(callback.data.replace("fav_page_", ""))
    except ValueError:
        page = 0
    await show_favorites_paged(callback, db_pool, bot, page=page)


async def show_favorites_paged(callback: types.CallbackQuery, db_pool,
                                bot: Bot, page: int = 0):
    """Yordamchi funksiya: sahifalab ko'rsatish"""
    async with db_pool.acquire() as conn:
        # 1. info_json ustuni borligini tekshirish
        has_info_col = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'favorites' 
                AND column_name = 'info_json'
            )
        """)

        # 2. Tegishli so'rov
        if has_info_col:
            favs = await conn.fetch(
                "SELECT candidate_id, info_json "
                "FROM favorites WHERE owner_id = $1 "
                "ORDER BY id DESC",
                callback.from_user.id
            )
        else:
            favs = await conn.fetch(
                "SELECT candidate_id "
                "FROM favorites WHERE owner_id = $1 "
                "ORDER BY id DESC",
                callback.from_user.id
            )

    if not favs:
        return await callback.answer(
            "⭐ Saralangan nomzodlar hozircha yo'q.",
            show_alert=True
        )

    total_count = len(favs)
    if page < 0:
        page = 0
    if page >= total_count:
        page = total_count - 1

    f = favs[page]
    candidate_id = f['candidate_id']

    # 3. Ma'lumotlarni olish
    data = {}
    if has_info_col and f.get('info_json'):
        try:
            data = json.loads(f['info_json'])
        except (json.JSONDecodeError, TypeError):
            data = {}

    # Agar info_json bo'sh bo'lsa, users jadvalidan olishga harakat
    if not data:
        async with db_pool.acquire() as conn:
            user_info = await conn.fetchrow(
                "SELECT full_name, age, category, experience "
                "FROM users WHERE user_id = $1",
                candidate_id
            )
        if user_info:
            if user_info.get('full_name'):
                data['full_name'] = user_info['full_name']
            if user_info.get('age'):
                data['age'] = str(user_info['age'])
            if user_info.get('category'):
                data['direction'] = user_info['category']
            if user_info.get('experience'):
                data['experience'] = user_info['experience']

    # 4. Matn tayyorlash
    summary = (
        f"⭐ <b>Saralangan nomzod ({page + 1}/{total_count})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Nomzod:</b> "
        f"<a href='tg://user?id={candidate_id}'>Profil</a>\n"
        f"🆔 <b>ID:</b> <code>{candidate_id}</code>\n"
    )

    pretty_names = {
        "full_name": "👤 Ism", "age": "🔢 Yosh",
        "phone": "📞 Tel", "experience": "⏳ Tajriba",
        "address": "📍 Manzil", "direction": "📍 Yo'nalish",
        "languages": "🌐 Tillar", "education": "🎓 Ma'lumot",
        "expected_salary": "💰 Maosh"
    }
    for key, val in data.items():
        if key not in ['photo', 'voice', 'candidate_name']:
            label = pretty_names.get(key, key.capitalize())
            summary += f"🔹 <b>{label}:</b> {val}\n"

    if not data or len(data) == 0:
        summary += "\nℹ️ <i>Batafsil ma'lumot mavjud emas</i>\n"

    reply_markup = get_fav_keyboard(candidate_id, page, total_count)

    # 5. Eski xabarni o'chirib yangisini yuborish
    try:
        await callback.message.delete()
    except Exception:
        pass

    try:
        if 'photo' in data and data['photo']:
            await callback.message.answer_photo(
                photo=data['photo'],
                caption=summary,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                summary,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"Favorites pagination xatosi: {e}")

    await callback.answer()


@router.callback_query(F.data.startswith("remove_fav_"))
async def remove_favorite(callback: types.CallbackQuery, db_pool, bot: Bot):
    parts = callback.data.split("_")
    candidate_id = int(parts[2])

    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM favorites "
            "WHERE owner_id = $1 AND candidate_id = $2",
            callback.from_user.id, candidate_id
        )

    await callback.answer("🗑 Ro'yxatdan o'chirildi.")
    await show_favorites_paged(callback, db_pool, bot, page=0)


# =====================================================
# 9-QISM: BALANS
# =====================================================

@router.callback_query(F.data == "balance")
async def show_balance(callback: types.CallbackQuery, db_pool):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT balance FROM users WHERE user_id = $1",
            callback.from_user.id
        )

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(
        text="➕ Balansni to'ldirish", callback_data="refill_balance"
    ))
    kb.row(types.InlineKeyboardButton(
        text="⬅️ Orqaga", callback_data="employer_panel"
    ))

    await callback.message.edit_text(
        f"💰 <b>Sizning balansingiz:</b> {user['balance']} ball\n\n"
        f"ℹ️ 1 ta e'lon joylashtirish = 10 ball",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "refill_balance")
async def send_invoice_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(
        text="⭐ 10 ball - 10 000 so'm", callback_data="xarid_10"
    ))
    kb.row(types.InlineKeyboardButton(
        text="⭐ 30 ball - 30 000 so'm", callback_data="xarid_30"
    ))
    kb.row(types.InlineKeyboardButton(
        text="⭐ 50 ball - 50 000 so'm", callback_data="xarid_50"
    ))
    kb.row(types.InlineKeyboardButton(
        text="⭐ 100 ball - 100 000 so'm", callback_data="xarid_100"
    ))
    kb.row(types.InlineKeyboardButton(
        text="⬅️ Orqaga", callback_data="balance"
    ))

    await callback.message.edit_text(
        "Kerakli paketni tanlang:", reply_markup=kb.as_markup()
    )


@router.callback_query(F.data.startswith("xarid_"))
async def process_xarid_ball(callback: types.CallbackQuery, bot: Bot):
    try:
        ball_amount = int(callback.data.split("_")[1])
    except Exception:
        return await callback.answer("❌ Xarid ma'lumotida xato!")

    prices_map = {10: 10000, 30: 30000, 50: 50000, 100: 100000}
    selected_price = prices_map.get(ball_amount)
    invoice_payload = f"refill_ball_{ball_amount}"

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"💳 {ball_amount} ball sotib olish",
        description=f"Korgoh: Hisobingizga {ball_amount} ball qo'shiladi.",
        provider_token=os.getenv("CLICK_TOKEN"),
        currency="UZS",
        prices=[types.LabeledPrice(
            label=f"{ball_amount} ball",
            amount=selected_price * 100
        )],
        payload=invoice_payload,
        start_parameter="refill",
        is_flexible=False
    )
    await callback.answer()


# =====================================================
# 10-QISM: E'LONLARNI KO'RISH VA O'CHIRISH
# =====================================================

@router.callback_query(F.data == "view_my_ads")
async def show_my_sectors(callback: types.CallbackQuery, db_pool):
    async with db_pool.acquire() as conn:
        sectors = await conn.fetch(
            "SELECT DISTINCT soha FROM ads WHERE owner_id = $1",
            callback.from_user.id
        )

    kb = InlineKeyboardBuilder()
    if not sectors:
        return await callback.answer(
            "Sizda hozircha faol e'lonlar yo'q.", show_alert=True
        )

    for s in sectors:
        kb.row(types.InlineKeyboardButton(
            text=f"📁 {s['soha']}",
            callback_data=f"del_sec_{s['soha']}"
        ))
    kb.row(types.InlineKeyboardButton(
        text="⬅️ Orqaga", callback_data="employer_panel"
    ))

    await callback.message.edit_text(
        "O'chirmoqchi bo'lgan e'loningiz sohasini tanlang:",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data.startswith("del_sec_"))
async def show_my_subs_to_delete(callback: types.CallbackQuery, db_pool):
    soha = callback.data.replace("del_sec_", "")
    async with db_pool.acquire() as conn:
        subs = await conn.fetch(
            "SELECT id, sub_sector FROM ads "
            "WHERE owner_id = $1 AND soha = $2",
            callback.from_user.id, soha
        )

    kb = InlineKeyboardBuilder()
    for sub in subs:
        kb.row(types.InlineKeyboardButton(
            text=f"📍 {sub['sub_sector']}",
            callback_data=f"confirm_del_{sub['id']}"
        ))
    kb.row(types.InlineKeyboardButton(
        text="⬅️ Orqaga", callback_data="view_my_ads"
    ))

    await callback.message.edit_text(
        f"<b>{soha}</b> sohasidagi qaysi e'lonni o'chirmoqchisiz?",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("confirm_del_"))
async def confirm_delete_ad(callback: types.CallbackQuery, db_pool):
    ad_id = int(callback.data.split("_")[2])

    async with db_pool.acquire() as conn:
        ad = await conn.fetchrow("""
            SELECT a.soha, a.sub_sector, r.room_number
            FROM ads a
            JOIN rooms r ON a.owner_id = r.owner_id
            WHERE a.id = $1
        """, ad_id)

    if not ad:
        return await callback.answer("E'lon topilmadi!")

    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(
            text="✅ Ha, o'chirilsin",
            callback_data=f"final_delete_{ad_id}"
        ),
        types.InlineKeyboardButton(
            text="❌ Yo'q, qolsin",
            callback_data="view_my_ads"
        )
    )

    await callback.message.edit_text(
        text=(
            f"⚠️ <b>DIQQAT!</b>\n\n"
            f"Siz haqiqatdan ham <b>{ad['soha']}</b> -> "
            f"<b>{ad['sub_sector']}</b> e'lonini "
            f"o'chirib tashlamoqchimisiz?\n"
            f"Bu amalni ortga qaytarib bo'lmaydi!"
        ),
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("final_delete_"))
async def delete_ad(callback: types.CallbackQuery, db_pool):
    ad_id = int(callback.data.split("_")[2])

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM ads WHERE id = $1", ad_id)

    await callback.answer(
        "🗑 E'lon muvaffaqiyatli o'chirildi!", show_alert=True
    )
    await show_my_sectors(callback, db_pool)


# =====================================================
# 11-QISM: SOZLAMALAR
# =====================================================

@router.callback_query(F.data == "emp_settings")
async def employer_settings(callback: types.CallbackQuery, db_pool):
    user_id = callback.from_user.id

    async with db_pool.acquire() as conn:
        settings = await conn.fetchrow(
            "SELECT balance, "
            "(SELECT COUNT(*) FROM ads WHERE owner_id = $1) as ads_count "
            "FROM users WHERE user_id = $1",
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
    kb.row(types.InlineKeyboardButton(
        text="🔔 Bildirishnomalar: ✅ ON",
        callback_data="toggle_notif"
    ))
    kb.row(types.InlineKeyboardButton(
        text="💬 Avto-javob matni",
        callback_data="set_auto_reply"
    ))
    kb.row(types.InlineKeyboardButton(
        text="📈 Batafsil statistika",
        callback_data="view_analytics"
    ))
    kb.row(types.InlineKeyboardButton(
        text="🗑 Profilni o'chirish",
        callback_data="delete_profile_start"
    ))
    kb.row(types.InlineKeyboardButton(
        text="⬅️ Orqaga", callback_data="employer_panel"
    ))
    kb.adjust(1)

    await callback.message.edit_text(
        text, reply_markup=kb.as_markup(), parse_mode="Markdown"
    )


@router.callback_query(F.data == "view_analytics")
async def view_analytics(callback: types.CallbackQuery, db_pool):
    user_id = callback.from_user.id

    async with db_pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total_ads,
                SUM(COALESCE(view_count, 0)) as total_views,
                (SELECT COUNT(*) FROM favorites
                 WHERE owner_id = $1) as saved_candidates
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
    kb.row(types.InlineKeyboardButton(
        text="⬅️ Orqaga", callback_data="emp_settings"
    ))

    await callback.message.edit_text(
        text, reply_markup=kb.as_markup(), parse_mode="Markdown"
    )


# =====================================================
# 12-QISM: PROFILNI O'CHIRISH
# =====================================================

@router.callback_query(F.data == "delete_profile_start")
async def confirm_delete_profile(callback: types.CallbackQuery):
    text = (
        "⚠️ <b>DIQQAT: QAYTARIB BO'LMAS AMAL!</b>\n\n"
        "Profilni o'chirsangiz, quyidagi ma'lumotlar "
        "<b>butunlay yo'qoladi:</b>\n"
        "• Siz sotib olgan barcha xona raqamlari\n"
        "• Barcha e'lonlaringiz va statistikalar\n"
        "• Hisobingizdagi mavjud ballar (yulduzlar)\n"
        "• Saqlangan barcha nomzodlar\n\n"
        "<i>Tizimda siz haqingizda hech qanday "
        "ma'lumot qolmaydi. Buni tasdiqlaysizmi?</i>"
    )

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(
        text="❌ Yo'q, bekor qilish",
        callback_data="emp_settings"
    ))
    kb.row(types.InlineKeyboardButton(
        text="🗑 HA, HAMMASINI O'CHIRISH",
        callback_data="delete_profile_final"
    ))

    await callback.message.edit_text(
        text, reply_markup=kb.as_markup(), parse_mode="HTML"
    )


@router.callback_query(F.data == "delete_profile_final")
async def delete_profile_execution(callback: types.CallbackQuery,
                                     db_pool, state: FSMContext):
    user_id = callback.from_user.id

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM ads WHERE owner_id = $1", user_id
            )
            await conn.execute(
                "DELETE FROM rooms WHERE owner_id = $1", user_id
            )
            await conn.execute(
                "DELETE FROM favorites WHERE owner_id = $1", user_id
            )
            await conn.execute(
                "DELETE FROM users WHERE user_id = $1", user_id
            )

    await state.clear()

    await callback.message.edit_text(
        "👋 <b>Hisobingiz muvaffaqiyatli o'chirildi.</b>\n\n"
        "Siz bilan hamkorlik qilganimizdan xursandmiz. "
        "Yana qaytib kelishingizni kutamiz!",
        parse_mode="HTML"
    )
    await callback.answer("Profil o'chirildi", show_alert=True)
