import os
import sqlite3
from aiogram import Bot, Dispatcher, executor, types

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# DATABASE
conn = sqlite3.connect("smm.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    service TEXT,
    link TEXT,
    amount INTEGER,
    status TEXT
)
""")

conn.commit()

user_data = {}

# START
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    user_id = msg.from_user.id

    cursor.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
    conn.commit()

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🛒 Xizmatlar")
    kb.add("💰 Balans", "📦 Buyurtmalarim")

    await msg.answer("🚀 SMM MARKET UZ botiga xush kelibsiz!", reply_markup=kb)

# BALANS
@dp.message_handler(lambda msg: msg.text == "💰 Balans")
async def balance(msg: types.Message):
    cursor.execute("SELECT balance FROM users WHERE id=?", (msg.from_user.id,))
    bal = cursor.fetchone()[0]

    await msg.answer(f"💰 Balans: {bal} so‘m")

# XIZMATLAR
@dp.message_handler(lambda msg: msg.text == "🛒 Xizmatlar")
async def services(msg: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👥 Telegram Obunachi")
    kb.add("❤️ Instagram Like")
    kb.add("🔙 Orqaga")

    await msg.answer("📦 Xizmat tanlang:", reply_markup=kb)

# BUYURTMA BOSHLASH
@dp.message_handler(lambda msg: msg.text in ["👥 Telegram Obunachi", "❤️ Instagram Like"])
async def order_start(msg: types.Message):
    user_data[msg.from_user.id] = {"service": msg.text}
    await msg.answer("🔗 Link yuboring:")

@dp.message_handler(lambda msg: msg.from_user.id in user_data and "link" not in user_data[msg.from_user.id])
async def get_link(msg: types.Message):
    user_data[msg.from_user.id]["link"] = msg.text
    await msg.answer("🔢 Miqdor yozing:")

@dp.message_handler(lambda msg: msg.from_user.id in user_data and "amount" not in user_data[msg.from_user.id])
async def get_amount(msg: types.Message):
    try:
        amount = int(msg.text)
    except:
        return await msg.answer("❌ Raqam yoz!")

    data = user_data[msg.from_user.id]
    data["amount"] = amount

    # oddiy narx
    price = amount * 10

    cursor.execute("INSERT INTO orders (user_id, service, link, amount, status) VALUES (?, ?, ?, ?, ?)",
                   (msg.from_user.id, data["service"], data["link"], amount, "Kutilmoqda"))

    conn.commit()

    await msg.answer("✅ Buyurtma qabul qilindi!")

    # ADMIN GA XABAR
    await bot.send_message(
        ADMIN_ID,
        f"🆕 Buyurtma\n\n"
        f"👤 {msg.from_user.id}\n"
        f"📦 {data['service']}\n"
        f"🔗 {data['link']}\n"
        f"🔢 {amount}"
    )

    del user_data[msg.from_user.id]

# BUYURTMALAR
@dp.message_handler(lambda msg: msg.text == "📦 Buyurtmalarim")
async def my_orders(msg: types.Message):
    cursor.execute("SELECT service, amount, status FROM orders WHERE user_id=?", (msg.from_user.id,))
    orders = cursor.fetchall()

    if not orders:
        return await msg.answer("📭 Buyurtma yo‘q")

    text = "📦 Buyurtmalar:\n\n"
    for o in orders:
        text += f"{o[0]} | {o[1]} dona | {o[2]}\n"

    await msg.answer(text)

# RUN
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
