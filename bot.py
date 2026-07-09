"""
Maktab Maslahatchisi Telegram Bot
- 4 asosiy menyu
- O'quvchi profili boshqaruvi
- Claude AI orqali ijtimoiy portfel
- SQLite + Google Sheets saqlash
- 24/7 ishlash
"""

import asyncio
import logging
import os
import sqlite3
import sys
from datetime import datetime

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)
from telegram.constants import ParseMode
import anthropic

# ─── SOZLAMALAR ────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_KEY")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

# ─── CONVERSATION STATES ───────────────────────────────────────────────────────
(
    MAIN_MENU,
    ADD_STUDENT_NAME, ADD_STUDENT_CLASS, ADD_STUDENT_DATA,
    SEARCH_STUDENT,
    PORTFOLIO_REQUEST,
    CLUBS_MENU, MONITORING_MENU,
) = range(8)

# ─── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── DATABASE ──────────────────────────────────────────────────────────────────
DB_PATH = "maktab.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            class_name TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS student_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER REFERENCES students(id),
            media_type TEXT,
            content TEXT,
            caption TEXT,
            added_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS clubs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            direction TEXT,
            responsible TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS club_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER REFERENCES clubs(id),
            student_id INTEGER REFERENCES students(id),
            joined_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER REFERENCES students(id),
            title TEXT,
            description TEXT,
            achievement_type TEXT,
            date TEXT,
            added_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS career_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER REFERENCES students(id),
            interest TEXT,
            university TEXT,
            profession TEXT,
            notes TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()
    logger.info("✅ Database tayyor")

def get_db():
    return sqlite3.connect(DB_PATH)

# ─── GOOGLE SHEETS ─────────────────────────────────────────────────────────────
def sync_to_sheets(student_data: dict):
    if not GOOGLE_SHEET_ID:
        return
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        sheet.append_row([student_data.get("id"), student_data.get("full_name"),
                          student_data.get("class_name"), student_data.get("created_at")])
    except Exception as e:
        logger.warning(f"⚠️ Google Sheets xatosi: {e}")

# ─── CLAUDE AI ─────────────────────────────────────────────────────────────────
def generate_portfolio(student_name: str, student_data: list) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    data_text = "\n".join([
        f"[{d['added_at'][:10]}] {d['media_type'].upper()}: {d['content']}"
        + (f" ({d['caption']})" if d['caption'] else "")
        for d in student_data
    ])
    prompt = f"""Siz maktab maslahatchisisiz. Quyidagi o'quvchi haqida to'plangan ma'lumotlar asosida professional IJTIMOIY PORTFEL tayyorlang.

O'quvchi ismi: {student_name}

To'plangan ma'lumotlar:
{data_text}

Portfelni quyidagi tuzilmada yozing (O'zbek tilida):

📋 IJTIMOIY PORTFEL: {student_name}
━━━━━━━━━━━━━━━━━━━━━━━━

👤 UMUMIY MA'LUMOT
[O'quvchi haqida qisqacha]

🏆 YUTUQLAR VA MUVAFFAQIYATLAR
[Barcha yutuqlarini sanab o'ting]

🎭 TO'GARAKLAR VA FAOLIYATLAR
[Qaysi to'garaklarda ishtirok etishi]

🎯 KELAJAK REJALARI
[Kasb tanlash, universitet istiqbollari]

💡 SHAXSIY SIFATLAR
[Ma'lumotlardan kelib chiqqan holda]

📊 MASLAHATCHI XULOSASI
[Umumiy baho va tavsiyalar]

━━━━━━━━━━━━━━━━━━━━━━━━
Sanalar, faktlar va aniq ma'lumotlarga asoslanib yozing."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

def ask_claude(question: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    system = """Siz maktab maslahatchisisining yordamchisisiz.
O'zbek tilida qisqa, aniq va foydali javoblar bering."""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": question}]
    )
    return message.content[0].text

# ─── KLAVIATURA ────────────────────────────────────────────────────────────────
def main_keyboard():
    keyboard = [
        [KeyboardButton("👨‍🎓 O'quvchilar boshqaruvi"), KeyboardButton("🏆 Yutuq va olimpiadalar")],
        [KeyboardButton("🎭 To'garaklar va yo'nalishlar"), KeyboardButton("🎯 Kasb yo'naltirish")],
        [KeyboardButton("📋 Portfel yaratish"), KeyboardButton("❓ AI maslahat")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, persistent=True)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def check_admin(update: Update) -> bool:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Kechirasiz, bu bot faqat maktab maslahatchisi uchun.")
        return False
    return True

# ─── START ─────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update):
        return
    user = update.effective_user
    welcome = f"""🏫 *Maktab Maslahatchisi Bot*

Assalomu alaykum, {user.first_name}!

Quyidagi menyudan foydalaning:"""
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN,
                                     reply_markup=main_keyboard())
    return MAIN_MENU

# ─── MENYU 1: O'QUVCHILAR ──────────────────────────────────────────────────────
async def students_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Yangi o'quvchi qo'shish", callback_data="add_student")],
        [InlineKeyboardButton("🔍 O'quvchi qidirish", callback_data="search_student")],
        [InlineKeyboardButton("📋 Barcha o'quvchilar", callback_data="list_students")],
    ]
    await update.message.reply_text(
        "👨‍🎓 *O'QUVCHILAR BOSHQARUVI*\n\nNima qilmoqchisiz?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def add_student_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "➕ O'quvchining to'liq ismini kiriting:\n_(Masalan: Karimov Jasur Aliyevich)_",
        parse_mode=ParseMode.MARKDOWN
    )
    return ADD_STUDENT_NAME

async def add_student_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_student_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ Ism: *{context.user_data['new_student_name']}*\n\nSinfini kiriting _(9-A, 11-B)_:",
        parse_mode=ParseMode.MARKDOWN
    )
    return ADD_STUDENT_CLASS

async def add_student_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data["new_student_name"]
    class_name = update.message.text.strip()
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO students (full_name, class_name) VALUES (?, ?)", (name, class_name))
    student_id = c.lastrowid
    conn.commit()
    sync_to_sheets({"id": student_id, "full_name": name,
                    "class_name": class_name, "created_at": datetime.now().isoformat()})
    conn.close()
    context.user_data["current_student_id"] = student_id
    await update.message.reply_text(
        f"✅ *{name}* ({class_name}) qo'shildi!\n🆔 ID: `{student_id}`\n\n"
        f"Ma'lumot qo'shish uchun: /add\\_media {student_id}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )
    return MAIN_MENU

async def search_student_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🔍 Ism yoki sinfni kiriting:")
    return SEARCH_STUDENT

async def search_student_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search = update.message.text.strip()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, full_name, class_name FROM students WHERE full_name LIKE ? OR class_name LIKE ? LIMIT 10",
              (f"%{search}%", f"%{search}%"))
    results = c.fetchall()
    conn.close()
    if not results:
        await update.message.reply_text("❌ Topilmadi.")
        return MAIN_MENU
    keyboard = [[InlineKeyboardButton(f"📋 {name} ({cls or '—'})", callback_data=f"student_profile_{sid}")]
                for sid, name, cls in results]
    await update.message.reply_text(f"🔍 *{len(results)} ta natija:*",
                                     parse_mode=ParseMode.MARKDOWN,
                                     reply_markup=InlineKeyboardMarkup(keyboard))
    return MAIN_MENU

async def show_student_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    student_id = int(query.data.split("_")[-1])
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT full_name, class_name, created_at FROM students WHERE id=?", (student_id,))
    student = c.fetchone()
    if not student:
        await query.message.reply_text("❌ Topilmadi.")
        conn.close()
        return
    name, cls, created = student
    c.execute("SELECT COUNT(*) FROM student_media WHERE student_id=?", (student_id,))
    media_count = c.fetchone()[0]
    conn.close()
    text = f"👤 *{name}*\n📚 Sinf: {cls or '—'}\n📅 {created[:10]}\n📁 Ma'lumotlar: {media_count} ta"
    keyboard = [
        [InlineKeyboardButton("📋 Portfel", callback_data=f"gen_portfolio_{student_id}")],
        [InlineKeyboardButton("📁 Ma'lumot qo'shish", callback_data=f"add_media_{student_id}")],
    ]
    await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=InlineKeyboardMarkup(keyboard))

# ─── MEDIA QO'SHISH ────────────────────────────────────────────────────────────
async def add_media_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update):
        return
    if not context.args:
        await update.message.reply_text("❗ Ishlatilishi: /add_media <id>")
        return
    try:
        student_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❗ ID raqam bo'lishi kerak.")
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT full_name FROM students WHERE id=?", (student_id,))
    student = c.fetchone()
    conn.close()
    if not student:
        await update.message.reply_text("❌ Bunday o'quvchi topilmadi.")
        return
    context.user_data["target_student_id"] = student_id
    context.user_data["target_student_name"] = student[0]
    await update.message.reply_text(
        f"📁 *{student[0]}* uchun ma'lumot yuboring:\n📝 Matn | 🖼 Rasm | 🎥 Video\n\nTugatish: /done",
        parse_mode=ParseMode.MARKDOWN
    )
    return ADD_STUDENT_DATA

async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_id = context.user_data.get("target_student_id")
    if not student_id:
        return MAIN_MENU
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    if update.message.text and not update.message.text.startswith("/"):
        c.execute("INSERT INTO student_media (student_id, media_type, content, added_at) VALUES (?,?,?,?)",
                  (student_id, "text", update.message.text, now))
        await update.message.reply_text("✅ Matn saqlandi!")
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
        c.execute("INSERT INTO student_media (student_id, media_type, content, caption, added_at) VALUES (?,?,?,?,?)",
                  (student_id, "photo", file_id, update.message.caption or "", now))
        await update.message.reply_text("✅ Rasm saqlandi!")
    elif update.message.video:
        file_id = update.message.video.file_id
        c.execute("INSERT INTO student_media (student_id, media_type, content, caption, added_at) VALUES (?,?,?,?,?)",
                  (student_id, "video", file_id, update.message.caption or "", now))
        await update.message.reply_text("✅ Video saqlandi!")
    elif update.message.document:
        file_id = update.message.document.file_id
        c.execute("INSERT INTO student_media (student_id, media_type, content, caption, added_at) VALUES (?,?,?,?,?)",
                  (student_id, "document", file_id, update.message.caption or "", now))
        await update.message.reply_text("✅ Hujjat saqlandi!")
    conn.commit()
    conn.close()
    return ADD_STUDENT_DATA

async def done_adding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get("target_student_name", "O'quvchi")
    context.user_data.pop("target_student_id", None)
    context.user_data.pop("target_student_name", None)
    await update.message.reply_text(
        f"✅ *{name}* uchun ma'lumot saqlash yakunlandi!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )
    return MAIN_MENU

# ─── MENYU 2: YUTUQLAR ─────────────────────────────────────────────────────────
async def achievements_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Barcha yutuqlar", callback_data="list_achievements")],
    ]
    await update.message.reply_text(
        "🏆 *YUTUQ VA OLIMPIADALAR*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def list_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT s.full_name, s.class_name, a.title, a.date
                 FROM achievements a JOIN students s ON a.student_id = s.id
                 ORDER BY a.added_at DESC LIMIT 20""")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await query.message.reply_text("📭 Hali yutuqlar kiritilmagan.")
        return
    text = "🏆 *SO'NGGI YUTUQLAR:*\n\n"
    for name, cls, title, date in rows:
        text += f"🥇 *{name}* ({cls or '—'}) — {title} | {date or '—'}\n"
    await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ─── MENYU 3: TO'GARAKLAR ─────────────────────────────────────────────────────
async def clubs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 Barcha to'garaklar", callback_data="list_clubs")],
    ]
    await update.message.reply_text(
        "🎭 *TO'GARAKLAR VA YO'NALISHLAR*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def list_clubs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, direction, responsible FROM clubs ORDER BY direction, name")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await query.message.reply_text("📭 Hali to'garaklar kiritilmagan.")
        return
    text = "🎭 *TO'GARAKLAR:*\n\n"
    for name, direction, responsible in rows:
        text += f"• *{name}* | {direction or '—'} | {responsible or '—'}\n"
    await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ─── MENYU 4: KASB YO'NALTIRISH ───────────────────────────────────────────────
async def career_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🏫 Top universitetlar", callback_data="universities_info")],
        [InlineKeyboardButton("🤖 AI maslahat", callback_data="ai_career_advice")],
    ]
    await update.message.reply_text(
        "🎯 *KASB YO'NALTIRISH*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def universities_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = """🏫 *TOP UNIVERSITETLAR*

🇺🇿 O'zbekiston: TDTU, NUU, INHA, Westminster
🌍 Xalqaro: MIT, Stanford, Oxford, KAIST, NUS

📝 Qabul: SAT, IELTS/TOEFL, milliy sertifikat"""
    await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ─── PORTFEL ───────────────────────────────────────────────────────────────────
async def portfolio_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 O'quvchi ismini yoki ID sini kiriting:",
        parse_mode=ParseMode.MARKDOWN
    )
    return PORTFOLIO_REQUEST

async def generate_portfolio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search = update.message.text.strip()
    conn = get_db()
    c = conn.cursor()
    if search.isdigit():
        c.execute("SELECT id, full_name FROM students WHERE id=?", (int(search),))
    else:
        c.execute("SELECT id, full_name FROM students WHERE full_name LIKE ? LIMIT 1", (f"%{search}%",))
    student = c.fetchone()
    if not student:
        await update.message.reply_text("❌ Topilmadi.")
        conn.close()
        return MAIN_MENU
    student_id, student_name = student
    c.execute("SELECT media_type, content, caption, added_at FROM student_media WHERE student_id=? ORDER BY added_at",
              (student_id,))
    media_rows = c.fetchall()
    conn.close()
    if not media_rows:
        await update.message.reply_text(
            f"⚠️ *{student_name}* haqida ma'lumot yo'q.\n/add\\_media {student_id} orqali qo'shing.",
            parse_mode=ParseMode.MARKDOWN
        )
        return MAIN_MENU
    await update.message.reply_text(f"⏳ *{student_name}* portfeli tayyorlanmoqda...", parse_mode=ParseMode.MARKDOWN)
    media_data = [{"media_type": r[0], "content": r[1], "caption": r[2], "added_at": r[3]} for r in media_rows]
    try:
        portfolio_text = generate_portfolio(student_name, media_data)
        await update.message.reply_text(portfolio_text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}", reply_markup=main_keyboard())
    return MAIN_MENU

# ─── AI MASLAHAT ───────────────────────────────────────────────────────────────
async def ai_advice_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ai_mode"] = True
    await update.message.reply_text(
        "🤖 *AI MASLAHAT*\n\nSavolingizni yozing:",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_ai_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("ai_mode"):
        return
    await update.message.reply_text("🤔 O'ylamoqdaman...")
    try:
        answer = ask_claude(update.message.text)
        context.user_data["ai_mode"] = False
        await update.message.reply_text(f"🤖 *AI Maslahat:*\n\n{answer}",
                                         parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}", reply_markup=main_keyboard())

# ─── CALLBACK DISPATCHER ──────────────────────────────────────────────────────
async def callback_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "add_student":
        return await add_student_start(update, context)
    elif data == "search_student":
        return await search_student_start(update, context)
    elif data == "list_achievements":
        return await list_achievements(update, context)
    elif data == "list_clubs":
        return await list_clubs(update, context)
    elif data == "universities_info":
        return await universities_info(update, context)
    elif data.startswith("student_profile_"):
        return await show_student_profile(update, context)
    elif data.startswith("gen_portfolio_"):
        student_id = int(data.split("_")[-1])
        await query.answer()
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT full_name FROM students WHERE id=?", (student_id,))
        row = c.fetchone()
        if row:
            await query.message.reply_text(f"⏳ *{row[0]}* portfeli...", parse_mode=ParseMode.MARKDOWN)
            c.execute("SELECT media_type, content, caption, added_at FROM student_media WHERE student_id=?", (student_id,))
            media_rows = c.fetchall()
            conn.close()
            if media_rows:
                media_data = [{"media_type": r[0], "content": r[1], "caption": r[2], "added_at": r[3]} for r in media_rows]
                try:
                    portfolio_text = generate_portfolio(row[0], media_data)
                    await query.message.reply_text(portfolio_text, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    await query.message.reply_text(f"❌ Xato: {e}")
            else:
                await query.message.reply_text(f"⚠️ Ma'lumot yo'q. /add_media {student_id}")
        else:
            conn.close()
    else:
        await query.answer("⚙️ Tez orada...")

# ─── ASOSIY MENYU ROUTER ──────────────────────────────────────────────────────
async def main_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update):
        return
    text = update.message.text
    routes = {
        "👨‍🎓 O'quvchilar boshqaruvi": students_menu,
        "🏆 Yutuq va olimpiadalar": achievements_menu,
        "🎭 To'garaklar va yo'nalishlar": clubs_menu,
        "🎯 Kasb yo'naltirish": career_menu,
        "📋 Portfel yaratish": portfolio_menu,
        "❓ AI maslahat": ai_advice_menu,
        "🏠 Bosh menyu": start,
    }
    if text in routes:
        result = await routes[text](update, context)
        if result == PORTFOLIO_REQUEST:
            return PORTFOLIO_REQUEST
        return MAIN_MENU
    if context.user_data.get("ai_mode"):
        await handle_ai_question(update, context)
        return MAIN_MENU
    if context.user_data.get("target_student_id"):
        return await receive_media(update, context)
    return MAIN_MENU

# ─── MAIN ──────────────────────────────────────────────────────────────────────
async def main():
    init_db()
    logger.info("🚀 Bot ishga tushmoqda...")

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.ALL & ~filters.COMMAND, main_menu_router),
                CallbackQueryHandler(callback_dispatcher),
            ],
            ADD_STUDENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_name)],
            ADD_STUDENT_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_class)],
            ADD_STUDENT_DATA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_media),
                MessageHandler(filters.PHOTO, receive_media),
                MessageHandler(filters.VIDEO, receive_media),
                MessageHandler(filters.Document.ALL, receive_media),
                CommandHandler("done", done_adding),
            ],
            SEARCH_STUDENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_student_result)],
            PORTFOLIO_REQUEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_portfolio_handler)],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^🏠 Bosh menyu$"), start),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("add_media", add_media_cmd))
    app.add_handler(CallbackQueryHandler(callback_dispatcher))

    logger.info("✅ Bot tayyor! Polling boshlandi...")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        logger.info("✅ Bot ishlayapti!")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
