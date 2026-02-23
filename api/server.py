import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="StudyScroll API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS_DIR = Path(__file__).parent.parent / "storage" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

WEBAPP_DIR = Path(__file__).parent.parent / "webapp"


# ── Session helpers ────────────────────────────────────────────────────────────

def create_session(topic: str, cards: list[dict]) -> str:
    """Persist a study session and return its ID."""
    session_id = str(uuid.uuid4())[:8]
    session_path = SESSIONS_DIR / f"{session_id}.json"
    session_path.write_text(json.dumps({"topic": topic, "cards": cards}, ensure_ascii=False))
    return session_id


def load_session(session_id: str) -> dict:
    """Load a session by ID."""
    session_path = SESSIONS_DIR / f"{session_id}.json"
    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    return json.loads(session_path.read_text())


# ── API routes ─────────────────────────────────────────────────────────────────

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Return the session's topic and cards as JSON."""
    session = load_session(session_id)
    return JSONResponse(content=session)


@app.get("/api/session/{session_id}/audio")
async def get_audio(session_id: str):
    """Stream the generated MP3 for a session."""
    audio_path = SESSIONS_DIR / f"{session_id}.mp3"
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not generated yet")
    return FileResponse(
        path=str(audio_path),
        media_type="audio/mpeg",
        filename=f"study_{session_id}.mp3"
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Serve the Mini App static files ───────────────────────────────────────────

app.mount("/", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")
