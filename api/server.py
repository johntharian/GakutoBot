import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update

from bot.main import build_bot_app
from storage import load_session, audio_exists, get_audio_path

logger = logging.getLogger(__name__)

# ── Telegram bot application ──────────────────────────────────────────────────

bot_app = build_bot_app()

WEBHOOK_PATH = "/webhook"
WEBAPP_BASE_URL = os.getenv("WEBAPP_BASE_URL", "http://localhost:8000")
WEBHOOK_URL = f"{WEBAPP_BASE_URL}{WEBHOOK_PATH}"


# ── FastAPI lifespan — register webhook on startup ────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize bot and set webhook
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")
    yield
    # Shutdown: clean up
    await bot_app.bot.delete_webhook()
    await bot_app.stop()
    await bot_app.shutdown()


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
    """Receive updates from Telegram and process them."""
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}


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
