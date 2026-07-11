"""
PDF -> Taqdimot Telegram bot.

Foydalanuvchi PDF kitob yuboradi, bot kerakli qismini AI yordamida
qisqartirib, tayyor .pptx taqdimot qilib qaytaradi.

Ishga tushirish:
    1. .env faylini to'ldiring (.env.example asosida)
    2. pip install -r requirements.txt
    3. python bot.py
"""

import logging
import os
import re
import tempfile

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

import pdf_utils
import ai_utils
import pptx_utils

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Suhbat holatlari
CHOOSING_RANGE, TYPING_RANGE = range(2)

MAX_PDF_MB = int(os.environ.get("MAX_PDF_MB", "20"))
LARGE_BOOK_PAGES = 40


# ---------- Buyruqlar ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum! 👋\n\n"
        "Men PDF darslik yoki kitobni taqdimotga aylantirib beraman.\n\n"
        "Boshlash uchun menga PDF fayl yuboring."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Qanday ishlataman:\n"
        "1. Menga PDF fayl yuboring\n"
        "2. Butun kitobni yoki kerakli sahifa oralig'ini tanlang\n"
        "3. Bir necha daqiqa kuting — AI matnni tahlil qilib, taqdimot tayyorlaydi\n"
        "4. Tayyor .pptx faylni oling\n\n"
        "/start — botni qayta boshlash\n"
        "/cancel — joriy amalni bekor qilish"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Bekor qilindi. Yangi PDF yuborishingiz mumkin.")
    return ConversationHandler.END


# ---------- PDF qabul qilish ----------

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    if not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Iltimos, faqat PDF fayl yuboring.")
        return ConversationHandler.END

    if document.file_size > MAX_PDF_MB * 1024 * 1024:
        await update.message.reply_text(
            f"Fayl juda katta ({MAX_PDF_MB} MB dan oshmasligi kerak)."
        )
        return ConversationHandler.END

    await update.message.chat.send_action(ChatAction.TYPING)

    tmp_dir = tempfile.mkdtemp()
    pdf_path = os.path.join(tmp_dir, "input.pdf")
    tg_file = await document.get_file()
    await tg_file.download_to_drive(pdf_path)

    try:
        page_count = pdf_utils.get_page_count(pdf_path)
    except Exception:
        await update.message.reply_text(
            "Faylni o'qib bo'lmadi. PDF buzilgan bo'lishi mumkin."
        )
        return ConversationHandler.END

    context.user_data["pdf_path"] = pdf_path
    context.user_data["page_count"] = page_count

    keyboard = [
        [InlineKeyboardButton("📘 Butun kitob", callback_data="range:full")],
        [InlineKeyboardButton("📑 Sahifa oralig'ini kiritaman", callback_data="range:custom")],
    ]
    warn = ""
    if page_count > LARGE_BOOK_PAGES:
        warn = (
            f"\n\n⚠️ Kitob {page_count} sahifadan iborat — butun kitobni tanlasangiz, "
            "natija juda umumiy bo'lishi mumkin. Aniqroq taqdimot uchun kerakli bo'lim "
            "sahifalarini kiritishni tavsiya qilamiz."
        )

    await update.message.reply_text(
        f"Fayl qabul qilindi ✅\nJami sahifalar: {page_count}{warn}\n\n"
        "Qaysi qismidan taqdimot tayyorlaylik?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_RANGE


async def choose_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "range:full":
        context.user_data["start_page"] = None
        context.user_data["end_page"] = None
        await query.edit_message_text("Butun kitob tanlandi. Ishlov berilmoqda... ⏳")
        return await process_and_send(update, context, use_query=True)

    await query.edit_message_text(
        "Sahifa oralig'ini kiriting.\n"
        "Masalan: 8-33 (8-sahifadan 33-sahifagacha)\n\n"
        f"(Jami sahifalar: {context.user_data.get('page_count')})"
    )
    return TYPING_RANGE


async def typed_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = re.match(r"^(\d+)\s*-\s*(\d+)$", text)

    if not match:
        await update.message.reply_text(
            "Formatni tushunmadim. Iltimos, shunday yozing: 8-33"
        )
        return TYPING_RANGE

    start_page, end_page = int(match.group(1)), int(match.group(2))
    page_count = context.user_data.get("page_count", 0)

    if start_page < 1 or end_page > page_count or start_page > end_page:
        await update.message.reply_text(
            f"Noto'g'ri oraliq. 1 dan {page_count} gacha kiriting."
        )
        return TYPING_RANGE

    context.user_data["start_page"] = start_page
    context.user_data["end_page"] = end_page

    await update.message.reply_text("Qabul qilindi. Ishlov berilmoqda... ⏳")
    return await process_and_send(update, context, use_query=False)


# ---------- Asosiy ishlov ----------

async def process_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, use_query: bool):
    chat = update.callback_query.message.chat if use_query else update.message.chat
    await chat.send_action(ChatAction.UPLOAD_DOCUMENT)

    pdf_path = context.user_data["pdf_path"]
    start_page = context.user_data.get("start_page")
    end_page = context.user_data.get("end_page")

    try:
        raw_text = pdf_utils.extract_text(pdf_path, start_page, end_page)
        raw_text = pdf_utils.truncate_for_model(raw_text)

        if len(raw_text.strip()) < 200:
            await chat.send_message(
                "Bu qismda yetarlicha matn topilmadi (rasm asosidagi sahifa bo'lishi mumkin)."
            )
            return ConversationHandler.END

        plan = ai_utils.generate_slide_plan(raw_text)

        tmp_out = tempfile.mktemp(suffix=".pptx")
        pptx_utils.build_presentation(plan, tmp_out)

        await chat.send_document(
            document=open(tmp_out, "rb"),
            filename="taqdimot.pptx",
            caption=f"Tayyor! 🎉 \"{plan.get('deck_title', 'Taqdimot')}\"",
        )

    except Exception as exc:
        logger.exception("Ishlov berishda xatolik")
        await chat.send_message(
            "Kechirasiz, ishlov berishda xatolik yuz berdi. Qaytadan urinib ko'ring.\n"
            f"(texnik tafsilot: {exc})"
        )
    finally:
        context.user_data.clear()

    return ConversationHandler.END


# ---------- Ilovani ishga tushirish ----------
    def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN topilmadi. .env faylini tekshiring.")

    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)

    use_local_api = os.environ.get("USE_LOCAL_BOT_API", "false").lower() == "true"
    if use_local_api:
        local_base = os.environ.get("LOCAL_BOT_API_URL", "http://localhost:8081")
        builder = builder.base_url(f"{local_base}/bot").base_file_url(f"{local_base}/file/bot")
        logger.info("Local Bot API server ishlatilyapti: %s", local_base)

    app = builder.build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.PDF, handle_document)],
        states={
            CHOOSING_RANGE: [CallbackQueryHandler(choose_range, pattern="^range:")],
            TYPING_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, typed_range)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(conv_handler)

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
