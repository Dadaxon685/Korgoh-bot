import pandas as pd
import datetime
from io import BytesIO

async def generate_employer_report(db_pool):
    async with db_pool.acquire() as conn:
        # 1. Tadbirkorlar haqida umumiy ma'lumot (Kim premium, kim faol)
        # Faollikni e'lonlar soni bo'yicha hisoblaymiz
        query = """
            SELECT 
                u.user_id, 
                u.full_name, 
                u.balance,
                u.role,
                r.room_type as premium_status,
                COUNT(a.id) as total_ads
            FROM users u
            LEFT JOIN rooms r ON u.user_id = r.owner_id
            LEFT JOIN ads a ON u.user_id = a.owner_id
            WHERE u.role = 'employer'
            GROUP BY u.user_id, r.room_type
            ORDER BY total_ads DESC
        """
        rows = await conn.fetch(query)
        
        # 2. Ma'lumotlarni DataFrame ga yuklash
        data = []
        for row in rows:
            data.append({
                "ID": row['user_id'],
                "Ism-Familiya": row['full_name'],
                "Balans (Ball)": row['balance'],
                "Tarif (Premium)": row['premium_status'] if row['premium_status'] else "Oddiy",
                "Joylagan e'lonlari": row['total_ads']
            })
        
        df = pd.DataFrame(data)
        
        # Excel faylini xotirada yaratish (Diskka saqlamasdan srazu yuborish uchun)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Tadbirkorlar_Hisoboti')
        
        output.seek(0)
        return output