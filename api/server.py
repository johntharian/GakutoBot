import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from storage import (
    create_session,
    load_session,
    audio_exists,
    get_audio_path,
)

app = FastAPI(title="StudyScroll API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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

from pathlib import Path
WEBAPP_DIR = Path(__file__).parent.parent / "webapp"
app.mount("/", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")
