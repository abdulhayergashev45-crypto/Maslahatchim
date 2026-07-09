"""
Darslikdan videoga/slaydga — Telegram bot.

Oqim:
  /start -> yosh guruhini tanlash -> matn yoki rasm yuborish
  -> formatni tanlash (slayd/video) -> Claude API -> fayl yaratish -> yuborish

Ishga tushirish:
  1) .env faylida TELEGRAM_BOT_TOKEN va ANTHROPIC_API_KEY ni to'ldiring
  2) pip install -r requirements.txt  (va ffmpeg tizimga o'rnatilgan bo'lsin)
  3) python bot.py
"""

import asyncio
import logging
import os
import tempfile

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters,
)

from content_generator import generate_scenes_from_text, generate_scenes_from_image
from slide_builder import build_pptx
from video_builder import build_video

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"].strip()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CHOOSE_LEVEL, WAITING_CONTENT, CHOOSE_FORMAT = range(3)

LEVEL_LABELS = {"1-4": "1–4 sinf", "5-9": "5–9 sinf", "10-11": "10–11 sinf"}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [[InlineKeyboardButton(label, callback_data=f"level:{key}")]
                for key, label in LEVEL_LABELS.items()]
    await update.message.reply_text(
        "Salom! Men darslik matnini (yoki rasmini) sodda tildagi animatsion "
        "video yoki taqdimotga aylantiraman.\n\n"
        "Avval o'quvchilar yosh guruhini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSE_LEVEL


async def on_level_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    level_key = query.data.split(":", 1)[1]
    context.user_data["level"] = level_key
    await query.edit_message_text(
        f"Daraja: {LEVEL_LABELS[level_key]} ✅\n\n"
        "Endi darslik matnini yuboring — yozib yuborishingiz ham, "
        "sahifaning suratini yuborishingiz ham mumkin."
    )
    return WAITING_CONTENT


async def on_content_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = bytes(await file.download_as_bytearray())
        context.user_data["content_type"] = "image"
        context.user_data["image_bytes"] = image_bytes
        context.user_data["media_type"] = "image/jpeg"
    elif update.message.text:
        context.user_data["content_type"] = "text"
        context.user_data["text"] = update.message.text
    else:
        await update.message.reply_text("Iltimos, matn yoki rasm yuboring.")
        return WAITING_CONTENT

    keyboard = [
        [InlineKeyboardButton("🖼️ Slayd (PPTX)", callback_data="format:slide")],
        [InlineKeyboardButton("🎬 Animatsion video", callback_data="format:video")],
    ]
    await update.message.reply_text(
        "Qabul qildim ✅ Endi qaysi formatda tayyorlab beray?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSE_FORMAT


async def on_format_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt = query.data.split(":", 1)[1]
    level = context.user_data.get("level", "5-9")

    status_msg = await query.edit_message_text("Sahnalar tayyorlanmoqda… ⏳")

    try:
        if context.user_data.get("content_type") == "image":
            scenes = generate_scenes_from_image(
                context.user_data["image_bytes"], context.user_data["media_type"],
                level, ANTHROPIC_API_KEY,
            )
        else:
            scenes = generate_scenes_from_text(
                context.user_data["text"], level, ANTHROPIC_API_KEY,
            )
    except Exception as exc:
        logger.exception("Sahnalar yaratishda xato")
        await status_msg.edit_text(f"Xatolik yuz berdi: {exc}\n\nQaytadan boshlash uchun /start ni bosing.")
        return ConversationHandler.END

    title = scenes[0].get("heading", "Darslik") if scenes else "Darslik"

    try:
        with tempfile.TemporaryDirectory() as tmp:
            if fmt == "slide":
                await status_msg.edit_text("Slaydlar tayyorlanmoqda… 🖼️")
                output_path = os.path.join(tmp, "darslik.pptx")
                await asyncio.to_thread(build_pptx, scenes, title, output_path)
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=open(output_path, "rb"),
                    filename="darslik.pptx",
                    caption=f"{len(scenes)} slaydli taqdimot tayyor ✅",
                )
            else:
                await status_msg.edit_text(
                    "Video tayyorlanmoqda… 🎬 (bu bir necha daqiqa vaqt olishi mumkin)"
                )
                output_path = os.path.join(tmp, "darslik.mp4")
                await asyncio.to_thread(
                    build_video, scenes, output_path, os.path.join(tmp, "work")
                )
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=open(output_path, "rb"),
                    caption=f"{len(scenes)} sahnali animatsion video tayyor ✅",
                )
        await status_msg.delete()
    except Exception as exc:
        logger.exception("Fayl yaratishda xato")
        await status_msg.edit_text(f"Fayl tayyorlashda xatolik: {exc}\n\nQaytadan boshlash uchun /start ni bosing.")
        return ConversationHandler.END

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Yana video/slayd tayyorlash uchun /start ni bosing.",
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Bekor qilindi. Qayta boshlash uchun /start ni bosing.")
    return ConversationHandler.END


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_LEVEL: [CallbackQueryHandler(on_level_chosen, pattern=r"^level:")],
            WAITING_CONTENT: [
                MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), on_content_received)
            ],
            CHOOSE_FORMAT: [CallbackQueryHandler(on_format_chosen, pattern=r"^format:")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    logger.info("Bot ishga tushdi.")
    app.run_polling()


if __name__ == "__main__":
    main()
