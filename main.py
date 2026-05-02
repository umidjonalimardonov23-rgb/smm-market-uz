import os
import sqlite3
import requests
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CARD_NUMBER = os.getenv("CARD_NUMBER", "KARTA YO‘Q")
SMM_API_URL = os.getenv("SMM_API_URL")
SMM_API_KEY = os.getenv("SMM_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

db = sqlite3.connect("smm.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    service_id INTEGER,
    service_name TEXT,
    link TEXT,
    quantity INTEGER,
    price INTEGER,
    api_order TEXT,
    status TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS payments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    status TEXT
)
""")
db.commit()

steps = {}
cached_services = []

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📁 Buyurtma berish", "📊 Buyurtmalarim")
    kb.add("💵 Mening hisobim", "💰 Hisob to‘ldirish")
    kb.add("☎️ Murojaat qilish", "👑 Admin panel")
    return kb

def api_request(data):
    data["key"] = SMM_API_KEY
    try:
        r = requests.post(SMM_API_URL, data=data, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def load_services():
    global cached_services
    res = api_request({"action": "services"})
    if isinstance(res, list):
        cached_services = res
    return cached_services

def calc_price(rate, quantity):
    api_price = float(rate) * quantity / 1000
    profit = api_price * 0.35
    return int(api_price + profit)

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    cur.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (msg.from_user.id,))
    db.commit()

    await msg.answer(
        "🚀 <b>SMM MARKET UZ</b>\n\n"
        "📲 Telegram | Instagram | TikTok\n"
        "👥 Obunachi • ❤️ Like • 👀 Ko‘rish\n\n"
        "Kerakli bo‘limni tanlang 👇",
        reply_markup=main_menu()
    )

@dp.message_handler(lambda m: m.text == "📁 Buyurtma berish")
async def categories(msg: types.Message):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📱 Telegram", callback_data="cat_Telegram"),
        InlineKeyboardButton("📸 Instagram", callback_data="cat_Instagram"),
        InlineKeyboardButton("🎵 TikTok", callback_data="cat_TikTok"),
        InlineKeyboardButton("▶️ YouTube", callback_data="cat_YouTube"),
    )
    await msg.answer("📁 Kategoriya tanlang:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("cat_"))
async def show_services(call: types.CallbackQuery):
    cat = call.data.replace("cat_", "")
    services = load_services()

    found = []
    for s in services:
        name = s.get("name", "")
        if cat.lower() in name.lower():
            found.append(s)

    if not found:
        await call.message.answer("❌ Xizmat topilmadi.")
        return await call.answer()

    kb = InlineKeyboardMarkup(row_width=1)
    for s in found[:40]:
        sid = s.get("service")
        name = s.get("name", "No name")[:55]
        rate = s.get("rate", "0")
        kb.add(InlineKeyboardButton(f"{name} | {rate} so‘m", callback_data=f"svc_{sid}"))

    await call.message.answer(f"📦 {cat} xizmatlari:", reply_markup=kb)
    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("svc_"))
async def choose_service(call: types.CallbackQuery):
    sid = int(call.data.replace("svc_", ""))
    services = cached_services or load_services()

    service = None
    for s in services:
        if int(s.get("service")) == sid:
            service = s
            break

    if not service:
        await call.message.answer("❌ Xizmat topilmadi.")
        return await call.answer()

    steps[call.from_user.id] = {
        "step": "link",
        "service": service
    }

    await call.message.answer(
        f"📦 <b>{service.get('name')}</b>\n\n"
        f"💰 Narx: {service.get('rate')} so‘m / 1000\n"
        f"🔢 Min: {service.get('min')} | Max: {service.get('max')}\n\n"
        f"🔗 Link yuboring:"
    )
    await call.answer()

@dp.message_handler(lambda m: m.from_user.id in steps and steps[m.from_user.id]["step"] == "link")
async def get_link(msg: types.Message):
    if not msg.text.startswith("http"):
        return await msg.answer("❌ Link https:// bilan boshlansin.")

    steps[msg.from_user.id]["link"] = msg.text
    steps[msg.from_user.id]["step"] = "quantity"
    await msg.answer("🔢 Miqdorni kiriting:")

@dp.message_handler(lambda m: m.from_user.id in steps and steps[m.from_user.id]["step"] == "quantity")
async def get_quantity(msg: types.Message):
    try:
        qty = int(msg.text)
    except:
        return await msg.answer("❌ Faqat raqam yozing.")

    data = steps[msg.from_user.id]
    service = data["service"]

    min_q = int(service.get("min", 1))
    max_q = int(service.get("max", 999999))

    if qty < min_q or qty > max_q:
        return await msg.answer(f"❌ Miqdor {min_q} dan {max_q} gacha bo‘lishi kerak.")

    price = calc_price(service.get("rate", 0), qty)

    cur.execute("SELECT balance FROM users WHERE id=?", (msg.from_user.id,))
    balance = cur.fetchone()[0]

    if balance < price:
        return await msg.answer(
            f"❌ Balans yetarli emas.\n\n"
            f"💰 Kerak: {price} so‘m\n"
            f"💵 Sizda: {balance} so‘m"
        )

    await msg.answer("⏳ Buyurtma API ga yuborilmoqda...")

    res = api_request({
        "action": "add",
        "service": service.get("service"),
        "link": data["link"],
        "quantity": qty
    })

    if "order" not in res:
        return await msg.answer(f"❌ API xato:\n<code>{res}</code>")

    api_order = str(res["order"])

    cur.execute("UPDATE users SET balance = balance - ? WHERE id=?", (price, msg.from_user.id))
    cur.execute("""
    INSERT INTO orders(user_id, service_id, service_name, link, quantity, price, api_order, status)
    VALUES(?,?,?,?,?,?,?,?)
    """, (
        msg.from_user.id,
        service.get("service"),
        service.get("name"),
        data["link"],
        qty,
        price,
        api_order,
        "✅ Yuborildi"
    ))
    db.commit()

    await msg.answer(
        f"✅ Buyurtma qabul qilindi!\n\n"
        f"📦 {service.get('name')}\n"
        f"🔢 {qty} dona\n"
        f"💰 {price} so‘m\n"
        f"🆔 Order: {api_order}"
    )

    await bot.send_message(
        ADMIN_ID,
        f"🆕 Yangi buyurtma\n\n"
        f"👤 User: <code>{msg.from_user.id}</code>\n"
        f"📦 {service.get('name')}\n"
        f"🔗 {data['link']}\n"
        f"🔢 {qty}\n"
        f"💰 {price} so‘m\n"
        f"🆔 {api_order}"
    )

    del steps[msg.from_user.id]

@dp.message_handler(lambda m: m.text == "💵 Mening hisobim")
async def account(msg: types.Message):
    cur.execute("SELECT balance FROM users WHERE id=?", (msg.from_user.id,))
    bal = cur.fetchone()[0]

    await msg.answer(
        f"💵 <b>Mening hisobim</b>\n\n"
        f"🆔 ID: <code>{msg.from_user.id}</code>\n"
        f"💰 Balans: <b>{bal} so‘m</b>"
    )

@dp.message_handler(lambda m: m.text == "💰 Hisob to‘ldirish")
async def refill(msg: types.Message):
    steps[msg.from_user.id] = {"step": "pay"}

    await msg.answer(
        f"💳 Karta:\n<code>{CARD_NUMBER}</code>\n\n"
        f"To‘lov summasini yozing:"
    )

@dp.message_handler(lambda m: m.from_user.id in steps and steps[m.from_user.id]["step"] == "pay")
async def pay_amount(msg: types.Message):
    try:
        amount = int(msg.text)
    except:
        return await msg.answer("❌ Summani raqam bilan yozing.")

    cur.execute("INSERT INTO payments(user_id, amount, status) VALUES(?,?,?)", (
        msg.from_user.id,
        amount,
        "⏳ Kutilmoqda"
    ))
    pay_id = cur.lastrowid
    db.commit()

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"payok_{pay_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"payno_{pay_id}")
    )

    await bot.send_message(
        ADMIN_ID,
        f"💳 To‘lov so‘rovi\n\n"
        f"🆔 ID: {pay_id}\n"
        f"👤 User: <code>{msg.from_user.id}</code>\n"
        f"💰 Summa: {amount} so‘m",
        reply_markup=kb
    )

    await msg.answer("✅ To‘lov so‘rovi adminga yuborildi.")
    del steps[msg.from_user.id]

@dp.callback_query_handler(lambda c: c.data.startswith("payok_"))
async def pay_ok(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin emassiz", show_alert=True)

    pay_id = int(call.data.replace("payok_", ""))
    cur.execute("SELECT user_id, amount FROM payments WHERE id=?", (pay_id,))
    row = cur.fetchone()

    if not row:
        return await call.answer("Topilmadi")

    user_id, amount = row

    cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, user_id))
    cur.execute("UPDATE payments SET status=? WHERE id=?", ("✅ Tasdiqlandi", pay_id))
    db.commit()

    await bot.send_message(user_id, f"✅ To‘lov tasdiqlandi!\n💰 Balansga qo‘shildi: {amount} so‘m")
    await call.message.edit_text("✅ To‘lov tasdiqlandi.")
    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("payno_"))
async def pay_no(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin emassiz", show_alert=True)

    pay_id = int(call.data.replace("payno_", ""))
    cur.execute("SELECT user_id FROM payments WHERE id=?", (pay_id,))
    row = cur.fetchone()

    if row:
        await bot.send_message(row[0], "❌ To‘lov rad etildi.")

    cur.execute("UPDATE payments SET status=? WHERE id=?", ("❌ Rad etildi", pay_id))
    db.commit()

    await call.message.edit_text("❌ To‘lov rad etildi.")
    await call.answer()

@dp.message_handler(lambda m: m.text == "📊 Buyurtmalarim")
async def orders(msg: types.Message):
    cur.execute("""
    SELECT service_name, quantity, price, api_order, status
    FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10
    """, (msg.from_user.id,))
    rows = cur.fetchall()

    if not rows:
        return await msg.answer("📭 Buyurtmalar yo‘q.")

    text = "📊 <b>Oxirgi buyurtmalar:</b>\n\n"
    for r in rows:
        text += (
            f"📦 {r[0]}\n"
            f"🔢 {r[1]} dona\n"
            f"💰 {r[2]} so‘m\n"
            f"🆔 {r[3]}\n"
            f"📌 {r[4]}\n\n"
        )

    await msg.answer(text)

@dp.message_handler(lambda m: m.text == "☎️ Murojaat qilish")
async def contact(msg: types.Message):
    await msg.answer("☎️ Admin: @username")

@dp.message_handler(lambda m: m.text == "👑 Admin panel")
async def admin(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return await msg.answer("❌ Siz admin emassiz.")

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM orders")
    orders_count = cur.fetchone()[0]

    await msg.answer(
        f"👑 <b>Admin panel</b>\n\n"
        f"👤 Users: {users}\n"
        f"📦 Orders: {orders_count}\n\n"
        f"Balans qo‘shish:\n"
        f"<code>/addbalance USER_ID SUMMA</code>"
    )

@dp.message_handler(commands=["addbalance"])
async def addbalance(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return

    try:
        _, user_id, amount = msg.text.split()
        user_id = int(user_id)
        amount = int(amount)
    except:
        return await msg.answer("❌ Format:\n/addbalance USER_ID SUMMA")

    cur.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (user_id,))
    cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, user_id))
    db.commit()

    await msg.answer("✅ Balans qo‘shildi.")
    await bot.send_message(user_id, f"💰 Balansingizga {amount} so‘m qo‘shildi.")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
