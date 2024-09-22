from environs import Env
import os
import re
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F

# Env obyektini yaratamiz
env = Env()
env.read_env()  # .env faylini o'qish

API_TOKEN = env.str("API_TOKEN")
ADMIN_CHAT_ID = env.str("ADMIN_CHAT_ID")
SECRET_CHANNEL_CHAT_ID=env.str('SECRET_CHANNEL_CHAT_ID')
DATABASE_PATH = 'order.db'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

user_data = {}

# Database yaratish va jadval tuzish
def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Jadval yaratish - orders
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        product TEXT NOT NULL
    )''')

    # Jadval yaratish - users
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL UNIQUE,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL
    )''')

    conn.commit()
    conn.close()

init_db()

async def is_valid_phone(phone: str) -> bool:
    return bool(re.match(r'^\+998\d{9}$', phone))

@dp.message(Command('start'))
async def start_command(message: Message):
    chat_id = message.from_user.id

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    user = cursor.fetchone()

    if user:
        await message.answer("Sizning ma'lumotlaringiz allaqon tayyor.")
    else:
        user_data[chat_id] = {}
        await message.answer("Ismingizni kiriting:")
        cursor.execute("INSERT INTO users (chat_id, name, phone, address) VALUES (?, ?, ?, ?)",
                       (chat_id, "", "", ""))
        conn.commit()

    conn.close()

@dp.message(lambda message: message.from_user.id in user_data and 'name' not in user_data[message.from_user.id])
async def get_name(message: Message):
    user_data[message.from_user.id]['name'] = message.text
    await message.answer("Telefon raqamingizni kiriting (+998XXXXXXXXX):")

@dp.message(lambda message: message.from_user.id in user_data and 'name' in user_data[message.from_user.id] and 'phone' not in user_data[message.from_user.id])
async def get_phone(message: Message):
    if await is_valid_phone(message.text):
        user_data[message.from_user.id]['phone'] = message.text
        await message.answer("Manzilingizni kiriting:")
    else:
        await message.answer("Telefon raqami noto'g'ri, qayta kiriting. (+998XXXXXXXXX formatida)")

@dp.message(lambda message: message.from_user.id in user_data and 'phone' in user_data[message.from_user.id] and 'address' not in user_data[message.from_user.id])
async def get_address(message: Message):
    user_data[message.from_user.id]['address'] = message.text

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''UPDATE users SET name = ?, phone = ?, address = ? WHERE chat_id = ?''',
                       (user_data[message.from_user.id]['name'],
                        user_data[message.from_user.id]['phone'], user_data[message.from_user.id]['address'], message.from_user.id))
        conn.commit()
        conn.close()

        await message.answer("Sizning ma'lumotlaringiz muvaffaqiyatli saqlandi.")
    except Exception as e:
        await message.answer(f"Xatolik yuz berdi: {e}")

products_info = {
    "Carwon Biostart": {"description": "3tasi 1da : Mobil ilova, Start-stop, KeylessGo", "image": "https://carwon.uz/img/prod2.b70090dc.png"},
    "Carwon Smart Trunk": {"description": "Oyoq harakati yordamida ochiluvchi yukxona sensori", "image": "https://carwon.uz/img/prod1.8b8008cc.png"},
    "Carwon Mobile app": {"description": "Carwon Mobile ilovasi avtomobilni eshiklari qulflarini ochish, yopish, yukxonasini ochish, dvigatelni ishga tushirish, yoki to’xtatish, avtomobilingizni ichki harorati, mator harorati va akkumulyatorning volti holatlarini masofadan bilish va boshqarish imkoniyatlarini beradi. ", "image": "https://res.cloudinary.com/dds8wmit7/image/upload/v1727030022/mqqbc0zxuqb54r7cparg.jpg"}
}

async def show_products(message: Message):
    product_inline_keyboard = [[InlineKeyboardButton(text=name, callback_data=name) for name in products_info.keys()]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=product_inline_keyboard)
    await message.answer("Mahsulotni tanlang:", reply_markup=keyboard)

@dp.callback_query(lambda callback_query: callback_query.data in products_info)
async def show_product_info(callback_query: types.CallbackQuery):
    user_data[callback_query.from_user.id]['product'] = callback_query.data

    product = products_info[callback_query.data]
    await bot.send_photo(chat_id=callback_query.message.chat.id, photo=product["image"])
    await callback_query.message.answer(f"Mahsulot: {callback_query.data}\nTavsif: {product['description']}")
    await callback_query.message.answer("Buyurtma tasdiqlansinmi? /ha yoki /yoq deb yozing.")

@dp.message(F.text == "/ha")
async def confirm_order(message: Message):
    user = user_data[message.from_user.id]

    order_message = (
        f"Yangi buyurtma!\n\n"
        f"Ism: {user['name']}\n"
        f"Telefon: {user['phone']}\n"
        f"Manzil: {user['address']}\n"
        f"Tanlangan mahsulot: {user['product']}"
    )

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO orders (name, phone, address, product) VALUES (?, ?, ?, ?)''',
                       (user['name'], user['phone'], user['address'], user['product']))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Xatolik: {e}")

    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=order_message)
    await bot.send_message(chat_id=SECRET_CHANNEL_CHAT_ID, text=order_message)
    await message.answer("Buyurtmangiz qabul qilindi. Tez orada bog'lanamiz.")

@dp.message(F.text == "/yoq")
async def cancel_order(message: Message):
    await message.answer("Buyurtma bekor qilindi. Iltimos, yana mahsulotni tanlang.")
    await show_products(message)

@dp.message(Command("buyurtma_qilish"))
async def buyurtma_berish(message: Message):
    chat_id = message.from_user.id

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    user = cursor.fetchone()

    if user:
        user_data[chat_id] = {
            'name': user[2],
            'phone': user[3],
            'address': user[4]
        }
        await message.answer("Ismingiz: {}\nTelefon raqamingiz: {}\nManzilingiz: {}\nMahsulotni tanlang:".format(user[2], user[3], user[4]))
        await show_products(message)
    else:
        await message.answer("Sizning ma'lumotlaringiz topilmadi. Iltimos, avval ro'yxatdan o'ting.")

@dp.message(Command('view_orders'))
async def view_orders(message: Message):
    if message.from_user.id != int(ADMIN_CHAT_ID):
        await message.answer("Sizda bu buyruqni bajarish huquqi yo'q.")
        return

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders")
        orders = cursor.fetchall()
        conn.close()

        if not orders:
            await message.answer("Hech qanday buyurtma topilmadi.")
            return

        orders_list = "\n\n".join([f"ID: {order[0]}, Ism: {order[1]}, Telefon: {order[2]}, Manzil: {order[3]}, Mahsulot: {order[4]}" for order in orders])
        await message.answer(f"Barcha buyurtmalar:\n\n{orders_list}")

    except Exception as e:
        print(f"Xatolik: {e}")
        await message.answer("Buyurtmalarni ko'rsatishda xatolik yuz berdi.")

@dp.message(Command('delete_order'))
async def delete_order(message: Message):
    if message.from_user.id != int(ADMIN_CHAT_ID):
        await message.answer("Sizda bu buyruqni bajarish huquqi yo'q.")
        return

    # Foydalanuvchi ma'lumotlari borligini tekshirish
    if message.from_user.id not in user_data:
        user_data[message.from_user.id] = {}

    # Foydalanuvchi ma'lumotlariga `delete_order`ni qo'shish
    user_data[message.from_user.id]['delete_order'] = True
    await message.answer("O'chiriladigan buyurtma ID sini kiriting:")



@dp.message(lambda message: user_data.get(message.from_user.id, {}).get('delete_order'))
async def process_delete_order(message: Message):
    try:
        order_id = int(message.text)
    except ValueError:
        await message.answer("Buyurtma ID noto'g'ri formatda, faqat raqam kiriting.")
        return

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

        if cursor.rowcount == 0:
            await message.answer(f"Buyurtma ID: {order_id} topilmadi.")
        else:
            await message.answer(f"Buyurtma ID: {order_id} muvaffaqiyatli o'chirildi.")

    except Exception as e:
        print(f"Xatolik: {e}")
        await message.answer("Buyurtmani o'chirishda xatolik yuz berdi.")

    # Jarayon tugadi, `delete_order`ni tozalash
    user_data[message.from_user.id].pop('delete_order', None)


@dp.message(Command("send_all"))
async def send_all(message: Message):
    if message.from_user.id != int(ADMIN_CHAT_ID):
        await message.answer("Sizda bu buyruqni bajarish huquqi yo'q.")
        return

    await message.answer("Yubormoqchi bo'lgan xabaringizni kiriting yoki fayl, rasm yoki video yuboring:")

    @dp.message(lambda msg: msg.from_user.id == int(ADMIN_CHAT_ID))
    async def get_message(admin_message: Message):
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id FROM users")
        users = cursor.fetchall()
        conn.close()

        if admin_message.text:
            message_type = 'text'
            content = admin_message.text
        elif admin_message.photo:
            message_type = 'photo'
            content = admin_message.photo[-1].file_id
        elif admin_message.video:
            message_type = 'video'
            content = admin_message.video.file_id
        elif admin_message.document:
            message_type = 'document'
            content = admin_message.document.file_id
        else:
            await admin_message.answer("Xabar turini aniqlashda muammo yuz berdi. Iltimos, matn, rasm, video yoki fayl yuboring.")
            return

        for user in users:
            try:
                if message_type == 'text':
                    await bot.send_message(chat_id=user[0], text=content)
                elif message_type == 'photo':
                    await bot.send_photo(chat_id=user[0], photo=content, caption=admin_message.caption or "")
                elif message_type == 'video':
                    await bot.send_video(chat_id=user[0], video=content, caption=admin_message.caption or "")
                elif message_type == 'document':
                    await bot.send_document(chat_id=user[0], document=content, caption=admin_message.caption or "")
            except Exception as e:
                print(f"Xatolik yuz berdi: {e}")

        await admin_message.answer("Xabar barcha foydalanuvchilarga yuborildi.")

@dp.message(Command("my_info"))
async def my_info(message: Message):
    chat_id = message.from_user.id

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        # Foydalanuvchi ma'lumotlarini ko'rsatish
        user_info = (
            f"Sizning ma'lumotlaringiz:\n\n"
            f"Ism: {user[2]}\n"
            f"Telefon: {user[3]}\n"
            f"Manzil: {user[4]}"
        )
        await message.answer(user_info)
    else:
        # Foydalanuvchini ro'yxatdan o'tish uchun /start komandasi orqali yo'naltirish
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. Iltimos, /start komandasini kiriting.")



@dp.message(Command('cancel'))
async def cancel_action(message: Message):
    user_id = message.from_user.id

    if user_id in user_data:
        user_data.pop(user_id)
        await message.answer("Barcha jarayonlar bekor qilindi.")
    else:
        await message.answer("Hozirda hech qanday jarayon mavjud emas.")

    # Bekor qilish jarayonlarini barcha funksiyalarda tekshirish
    for key in user_data:
        user_data[key]['cancelled'] = True

# Barcha ma'lumot yig'ish jarayonlarida cancel funksiyasini nazorat qilish
@dp.message(lambda message: user_data.get(message.from_user.id, {}).get('cancelled', False))
async def check_cancelled(message: Message):
    await message.answer("Jarayon bekor qilindi. /start orqali qayta boshlang.")


@dp.message(Command("update_info"))
async def start_update_info(message: Message):
    chat_id = message.from_user.id

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    user = cursor.fetchone()

    if user:
        user_data[chat_id] = {'update_info': True, 'field_index': 0}
        await message.answer("Ismingizni kiriting:")
    else:
        await message.answer("Sizning ma'lumotlaringiz topilmadi. Iltimos, avval ro'yxatdan o'ting.")

    conn.close()

@dp.message(lambda message: user_data.get(message.from_user.id, {}).get('update_info'))
async def process_update_info(message: Message):
    user_id = message.from_user.id
    field_index = user_data[user_id]['field_index']

    if field_index == 0:
        user_data[user_id]['name'] = message.text
        user_data[user_id]['field_index'] += 1
        await message.answer("Telefon raqamingizni kiriting (+998XXXXXXXXX):")
    elif field_index == 1:
        if await is_valid_phone(message.text):
            user_data[user_id]['phone'] = message.text
            user_data[user_id]['field_index'] += 1
            await message.answer("Manzilingizni kiriting:")
        else:
            await message.answer("Telefon raqami noto'g'ri, qayta kiriting. (+998XXXXXXXXX formatida)")
    elif field_index == 2:
        user_data[user_id]['address'] = message.text

        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute('''UPDATE users SET name = ?, phone = ?, address = ? WHERE chat_id = ?''',
                           (user_data[user_id]['name'],
                            user_data[user_id]['phone'], user_data[user_id]['address'], user_id))
            conn.commit()
            conn.close()

            await message.answer("Sizning ma'lumotlaringiz muvaffaqiyatli saqlandi.")
            user_data[user_id].pop('update_info', None)
            user_data[user_id].pop('field_index', None)
        except Exception as e:
            await message.answer(f"Xatolik yuz berdi: {e}")

if __name__ == "__main__":
    dp.run_polling(bot, skip_updates=True)