import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Add parent dir to path so we can import generator + api modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from generator.content import generate_study_cards, cards_to_audio_script
from generator.audio import generate_audio
from storage import create_session, save_audio, get_local_audio_path

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WEBAPP_BASE_URL = os.getenv("WEBAPP_BASE_URL", "http://localhost:8000")


# ── Handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *StudyScroll*!\n\n"
        "Send me any topic or question and I'll turn it into a scroll-friendly study feed with audio.\n\n"
        "Examples:\n"
        "• _How does photosynthesis work?_\n"
        "• _Explain the Cold War_\n"
        "• _Basics of machine learning_\n"
        "• _The Roman Empire_",
        parse_mode="Markdown"
    )


async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()

    if len(topic) < 3:
        await update.message.reply_text("Please send a topic with at least a few words!")
        return

    # Acknowledge immediately
    status_msg = await update.message.reply_text(
        f"🧠 Generating study feed for *{topic}*…\n\n"
        "_This takes ~10 seconds_",
        parse_mode="Markdown"
    )

    try:
        # 1. Generate cards
        await status_msg.edit_text(
            f"📚 Building cards for *{topic}*…",
            parse_mode="Markdown"
        )
        cards = await generate_study_cards(topic)
        logger.info(f"Generated {len(cards)} cards for topic: {topic}")

        # 2. Create session (saves JSON)
        session_id = create_session(topic, cards)

        # 3. Build the Mini App URL and send it immediately
        webapp_url = f"{WEBAPP_BASE_URL}?session={session_id}"
        await status_msg.delete()
        await update.message.reply_text(
            f"✅ Your study feed is ready!\n\n"
            f"📖 *{topic}*\n"
            f"• {len(cards)} cards\n"
            f"• 🎧 Audio generating…\n\n"
            f"Tap below to open your scroll feed 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "📖 Open Study Feed",
                    web_app=WebAppInfo(url=webapp_url)
                )
            ]])
        )

        # 4. Generate audio in the background, then send it
        try:
            script = cards_to_audio_script(topic, cards)
            audio_path = get_local_audio_path(session_id)
            await generate_audio(script, audio_path)
            save_audio(session_id, audio_path)
            logger.info(f"Audio saved: {audio_path}")

            await update.message.reply_audio(
                audio=open(audio_path, "rb"),
                title=f"Study: {topic}",
                caption="🎧 Audio version — listen while you scroll!"
            )
        except Exception as audio_err:
            logger.exception(f"Audio generation failed for {session_id}: {audio_err}")
            await update.message.reply_text(
                "⚠️ Audio generation failed, but your cards are still available!",
            )

    except Exception as e:
        logger.exception(f"Failed to generate session for topic: {topic}")
        await status_msg.edit_text(
            f"❌ Something went wrong: `{str(e)}`\n\nPlease try again.",
            parse_mode="Markdown"
        )


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Just send me any topic as a text message and I'll build your study feed!"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown))

    logger.info("StudyScroll bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
