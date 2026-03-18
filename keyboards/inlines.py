from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types

# Tariflar menyusi
def room_types_keyboard():
    builder = InlineKeyboardBuilder()
    
    # 1. Standart xonani "BEPUL" deb belgilaymiz
    builder.row(types.InlineKeyboardButton(
        text="🏢 Standart Xona (BEPUL)", 
        callback_data="buy_room_standard") # 'standard' koddagi state bilan bir xil bo'lishi kerak
    )
    
    # 2. Premium (Silver) xona
    builder.row(types.InlineKeyboardButton(
        text="🥈 Premium Xona (150,000 so'm)", 
        callback_data="buy_room_silver") # 'silver' koddagi lug'atga mos
    )
    
    # 3. VIP (Gold) xona
    builder.row(types.InlineKeyboardButton(
        text="👑 VIP Xona (500,000 so'm)", 
        callback_data="buy_room_gold") # 'gold' koddagi lug'atga mos
    )
    
    # 4. Orqaga tugmasini ham qo'shib qo'yamiz (har ehtimolga qarshi)
    builder.row(types.InlineKeyboardButton(
        text="⬅️ Bekor qilish", 
        callback_data="employer_panel")
    )
    
    builder.adjust(1)
    return builder.as_markup()
# To'lov turi menyusi
def payment_type_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Click", callback_data="pay_click_1"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="buy_room_start"))
    return builder.as_markup()

# Asosiy Boshqaruv Paneli (Sotib olgandan keyin)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types

# 🔍 1. ISH IZLOVCHI (NOMZOD) PANELI
def candidate_panel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔍 Ish qidirish", callback_data="find_job"))
    # builder.row(types.InlineKeyboardButton(text="📄 Mening anketam", callback_data="my_resume"))
    # builder.row(types.InlineKeyboardButton(text="📥 Arizalarim holati", callback_data="my_applications"))
    builder.row(types.InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="cand_settings"))
    builder.adjust(1)
    return builder.as_markup()

# 🏢 2. TADBIRKOR (ISH BERUVCHI) PANELI
def employer_panel_keyboard(room_number):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=f"🏢 Mening xonam: №{room_number}", callback_data="my_room"))
    builder.row(types.InlineKeyboardButton(text="➕ Yangi e'lon", callback_data="new_ad"))
    builder.row(types.InlineKeyboardButton(text="📋 Mening e'lonlarim", callback_data="view_my_ads"))
    builder.row(types.InlineKeyboardButton(text="⭐ Saqlangan nomzodlar", callback_data="view_favorites"))
    builder.row(types.InlineKeyboardButton(text="💰 Balans", callback_data="balance"), 
                types.InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="emp_settings"))
    builder.adjust(1, 1, 1, 2)
    return builder.as_markup()
# 👑 3. ADMIN PANELI
def admin_panel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📊 Umumiy statistika", callback_data="admin_stats"))
    # builder.row(types.InlineKeyboardButton(text="💳 To'lovlarni tasdiqlash", callback_data="confirm_payments"))
    builder.row(types.InlineKeyboardButton(text="📢 Hammaga xabar yuborish", callback_data="broadcast"))
    builder.row(types.InlineKeyboardButton(text="🚫 Foydalanuvchini bloklash", callback_data="block_user"))
    builder.row(types.InlineKeyboardButton(text="📁 Excel Hisobot (Tadbirkorlar)", callback_data="admin_report_excel"))
    builder.adjust(1)
    return builder.as_markup()



from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types

# 1. Sohalar menyusi
def sectors_keyboard():
    builder = InlineKeyboardBuilder()
    
    # O'zing xohlagan sohalarni shu ro'yxatga qo'shishing mumkin
    sectors = [
        "🩺 Tibbiyot", 
        "💻 IT", 
        "🏗 Qurilish", 
        "📞 Call-center", 
        "🚚 Logistika", 
        "🎓 Ta'lim", 
        "🍽 Restoran"
    ]
    
    for s in sectors:
        builder.row(types.InlineKeyboardButton(
            text=s, 
            callback_data=f"setsector_{s}")
        )
        
    builder.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="employer_panel"))
    return builder.as_markup()

# 2. Galochka (Requirements) tizimi
def requirements_keyboard(selected_list):
    builder = InlineKeyboardBuilder()
    
    # Tadbirkor xohlagan hamma narsani shu yerga qo'shish mumkin
    options = {
        "full_name": "Ism-familiya",
        "age": "Yoshi",
        "phone": "Telefon raqami",
        "photo": "Rasm (3x4)",
        "voice": "Ovozli xabar",
        "experience": "Ish tajribasi",
        "education": "Ma'lumoti",           # Yangi
        "languages": "Tillar",              # Yangi
        "expected_salary": "Maosh kutish",  # Yangi
        "address": "Yashash manzili",
        "portfolio": "Portfolio (Link/Fayl)"
    }    
    for key, label in options.items():
        status = "✅" if key in selected_list else "❌"
        builder.row(types.InlineKeyboardButton(text=f"{status} {label}", callback_data=f"req_{key}"))
    
    builder.row(types.InlineKeyboardButton(text="🚀 Tayyor! Keyin qadamga o'tish", callback_data="finish_ad"))
    builder.row(types.InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="employer_panel"))
    builder.adjust(1)
    return builder.as_markup()


def candidate_settings_keyboard(notifications_enabled=True):
    builder = InlineKeyboardBuilder()
    
    # Bildirishnoma holatiga qarab matnni tanlaymiz
    notif_status = "✅ Yoqilgan" if notifications_enabled else "❌ O'chirilgan"
    
    builder.row(types.InlineKeyboardButton(text=f"🔔 Bildirishnomalar: {notif_status}", callback_data="toggle_cand_notif"))
    builder.row(types.InlineKeyboardButton(text="🔄 Profilni tahrirlash", callback_data="create_profile"))
    builder.row(types.InlineKeyboardButton(text="🗑 Profilni o'chirish", callback_data="delete_my_profile"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="candidate_panel"))
    
    builder.adjust(1)
    return builder.as_markup()

def regions_keyboard():
    regions = [
        "Toshkent", "Andijon", "Farg'ona", "Namangan",
        "Samarqand", "Buxoro", "Xorazm", "Surxondaryo",
        "Qashqadaryo", "Jizzax", "Sirdaryo", "Navoiy", "Qoraqalpog'iston"
    ]
    kb = InlineKeyboardBuilder()
    for region in regions:
        kb.button(text=region, callback_data=f"reg_{region}")
    kb.adjust(2) # Tugmalarni 2 qatordan teradi
    return kb.as_markup()

def job_type_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🏠 Online (Masofaviy)", callback_data="type_Online")
    kb.button(text="🏢 Offline (Ofisda)", callback_data="type_Offline")
    return kb.as_markup()




def regions_keyboard():
    regions = [
        "Toshkent", "Andijon", "Farg'ona", "Namangan",
        "Samarqand", "Buxoro", "Xorazm", "Surxondaryo",
        "Qashqadaryo", "Jizzax", "Sirdaryo", "Navoiy", "Qoraqalpog'iston"
    ]
    kb = InlineKeyboardBuilder()
    for region in regions:
        kb.button(text=region, callback_data=f"reg_{region}")
    kb.adjust(2)
    # Oxiriga orqaga qaytish tugmasini ham qo'shsa bo'ladi
    return kb.as_markup()




def get_fav_keyboard(candidate_id, current_index, total_count):
    kb = InlineKeyboardBuilder()
    
    # 1-qator: Asosiy amallar
    kb.row(
        types.InlineKeyboardButton(text="📞 Bog'lanish", callback_data=f"contact_{candidate_id}"),
        types.InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"remove_fav_{candidate_id}_{current_index}")
    )
    
    # 2-qator: Navigatsiya (⬅️ 1/5 ➡️)
    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"fav_page_{current_index - 1}"))
    
    nav_buttons.append(types.InlineKeyboardButton(text=f"{current_index + 1}/{total_count}", callback_data="none"))
    
    if current_index < total_count - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"fav_page_{current_index + 1}"))
    
    kb.row(*nav_buttons)
    kb.row(types.InlineKeyboardButton(text="🏠 Menu", callback_data="employer_panel"))
    
    return kb.as_markup()
