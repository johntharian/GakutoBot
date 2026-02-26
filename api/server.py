import asyncio
import json
import logging
import os
import sys
import traceback
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update

from bot.main import build_bot_app
from storage import load_session, audio_exists, get_audio_path


# ── Structured JSON logging for Cloud Run ─────────────────────────────────────

class CloudRunFormatter(logging.Formatter):
    """Output JSON logs that Google Cloud Logging parses automatically."""
    LEVEL_MAP = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }

    def format(self, record):
        log = {
            "severity": self.LEVEL_MAP.get(record.levelname, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
        }
        if record.exc_info and record.exc_info[0]:
            log["exception"] = traceback.format_exception(*record.exc_info)
        return json.dumps(log)


def setup_logging():
    """Configure logging — JSON for Cloud Run, human-readable locally."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if os.getenv("K_SERVICE"):
        # Running on Cloud Run — use JSON format
        handler.setFormatter(CloudRunFormatter())
    else:
        # Local dev — use human-readable format
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))

    root.handlers.clear()
    root.addHandler(handler)


setup_logging()
logger = logging.getLogger("studyscroll")

# ── Telegram bot application ──────────────────────────────────────────────────

bot_app = build_bot_app()

WEBHOOK_PATH = "/webhook"
WEBAPP_BASE_URL = os.getenv("WEBAPP_BASE_URL", "http://localhost:8000")
WEBHOOK_URL = f"{WEBAPP_BASE_URL}{WEBHOOK_PATH}"

# Track recently processed update IDs to prevent duplicates
_processed_updates: OrderedDict[int, bool] = OrderedDict()
MAX_TRACKED_UPDATES = 1000

# Track background tasks to prevent Cloud Run from killing them
_background_tasks: set[asyncio.Task] = set()


# ── FastAPI lifespan — register webhook on startup ────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting up — WEBHOOK_URL={WEBHOOK_URL}")
    logger.info(f"WEBAPP_BASE_URL={WEBAPP_BASE_URL}")
    logger.info(f"GCS_BUCKET_NAME={os.getenv('GCS_BUCKET_NAME', 'NOT SET')}")
    logger.info(f"TELEGRAM_BOT_TOKEN={'SET' if os.getenv('TELEGRAM_BOT_TOKEN') else 'NOT SET'}")
    logger.info(f"GEMINI_API_KEY={'SET' if os.getenv('GEMINI_API_KEY') else 'NOT SET'}")

    await bot_app.initialize()
    await bot_app.start()
    await bot_app.bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook registered at {WEBHOOK_URL}")
    yield
    # Shutdown
    await bot_app.bot.delete_webhook()
    await bot_app.stop()
    await bot_app.shutdown()
    logger.info("Shutdown complete")


app = FastAPI(title="StudyScroll API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Telegram webhook endpoint ─────────────────────────────────────────────────

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Receive updates from Telegram — respond immediately, process in background."""
    try:
        data = await request.json()
        logger.info(f"Webhook received: {json.dumps(data)[:500]}")

        update = Update.de_json(data, bot_app.bot)
        logger.info(f"Update parsed: id={update.update_id}, type={'message' if update.message else 'other'}")

        if update.message:
            logger.info(f"Message from user {update.message.from_user.id}: '{update.message.text}'")

        # Deduplicate
        if update.update_id in _processed_updates:
            logger.info(f"Skipping duplicate update {update.update_id}")
            return {"ok": True}

        _processed_updates[update.update_id] = True
        if len(_processed_updates) > MAX_TRACKED_UPDATES:
            _processed_updates.popitem(last=False)

        # Process in background but keep a reference so it isn't garbage collected
        task = asyncio.create_task(_process_update_safe(update))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        return {"ok": True}

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


async def _process_update_safe(update: Update):
    """Process a Telegram update with full error logging."""
    try:
        logger.info(f"Processing update {update.update_id}")
        await bot_app.process_update(update)
        logger.info(f"Update {update.update_id} processed successfully")
    except Exception:
        logger.exception(f"Error processing update {update.update_id}")


# ── Debug endpoints ───────────────────────────────────────────────────────────

@app.get("/debug/status")
async def debug_status():
    """Check app health and configuration."""
    webhook_info = await bot_app.bot.get_webhook_info()
    return {
        "status": "ok",
        "env": {
            "TELEGRAM_BOT_TOKEN": "SET" if os.getenv("TELEGRAM_BOT_TOKEN") else "NOT SET",
            "GEMINI_API_KEY": "SET" if os.getenv("GEMINI_API_KEY") else "NOT SET",
            "ANTHROPIC_API_KEY": "SET" if os.getenv("ANTHROPIC_API_KEY") else "NOT SET",
            "WEBAPP_BASE_URL": os.getenv("WEBAPP_BASE_URL", "NOT SET"),
            "GCS_BUCKET_NAME": os.getenv("GCS_BUCKET_NAME", "NOT SET"),
        },
        "webhook": {
            "url": webhook_info.url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "last_error_date": str(webhook_info.last_error_date) if webhook_info.last_error_date else None,
            "last_error_message": webhook_info.last_error_message,
        },
        "background_tasks_active": len(_background_tasks),
        "updates_tracked": len(_processed_updates),
    }


# ── API routes ─────────────────────────────────────────────────────────────────

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Return the session's topic and cards as JSON."""
    session = load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return JSONResponse(content=session)


@app.get("/api/session/{session_id}/audio")
async def get_audio(session_id: str):
    """Stream the generated MP3 for a session."""
    path = get_audio_path(session_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Audio not generated yet")
    return FileResponse(
        path=path,
        media_type="audio/mpeg",
        filename=f"study_{session_id}.mp3"
    )


@app.get("/api/session/{session_id}/audio/status")
async def get_audio_status(session_id: str):
    """Check if the audio file has been generated yet."""
    return {"ready": audio_exists(session_id)}


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Serve the Mini App static files ───────────────────────────────────────────

WEBAPP_DIR = Path(__file__).parent.parent / "webapp"
app.mount("/", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")
