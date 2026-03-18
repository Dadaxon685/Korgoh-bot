from aiogram.fsm.state import State, StatesGroup

# class AdCreation(StatesGroup):
#     sector = State()        # Asosiy soha (IT, Tibbiyot, Qurilish...)
#     custom_service = State() # O'z xizmat turini yozish (Agar ro'yxatda bo'lmasa)
#     requirements = State()  # O'sha mashhur ✅/❌ Galochkalar
#     confirmation = State()  # Yakuniy tekshiruv
class AdCreation(StatesGroup):
    sector = State()          # Soha (IT, Dizayn va h.k.)
    custom_service = State()  # Yo'nalish (Backend, Stomatolog...)
    region = State()          # Qaysi viloyat
    job_type = State()        # Online / Offline
    salary = State()          # Maosh
    work_time = State()       # Ish vaqti
    requirements = State()    # Nomzodga qo'yilgan talablar (Galochkalar)
    confirm = State()
    reject_reason = State()
# class AdCreation(StatesGroup):
#     sector = State()
#     specialty = State()
#     requirements = State()

# from aiogram.fsm.state import State, StatesGroup

class JobSeeker(StatesGroup):
    waiting_room_num = State()   # Xona raqamini kutish
    choosing_sector = State()    # Sohani tanlash
    choosing_sub = State()       # Yo'nalishni tanlash
    filling_form = State()       # Anketani to'ldirish bosqichi)

class ContactState(StatesGroup):
    choosing_method = State() # Ovoz yoki Xabar tanlash
    waiting_voice = State()   # Ovoz yozish bosqichi
    waiting_details = State() # Uchrashuv sanasi va tel
    waiting_location = State() # Lokatsiya bosqichi



class CandidateProfile(StatesGroup):
    waiting_name = State()
    waiting_age = State()
    waiting_category = State() 
    waiting_custom_category = State()# Yo'nalishi (Masalan: Sotuvchi, Haydovchi)
    waiting_experience = State()
    waiting_photo = State()
    waiting_voice = State() # Ovozli tanishtiruv
from aiogram.fsm.state import State, StatesGroup

class EmployerReg(StatesGroup):
    waiting_name = State()
    waiting_phone = State()


