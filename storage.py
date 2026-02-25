"""
Storage abstraction — uses Google Cloud Storage when GCS_BUCKET_NAME is set,
falls back to local filesystem otherwise.
"""

import json
import os
import uuid
import tempfile
from pathlib import Path

# ── Local fallback ────────────────────────────────────────────────────────────

LOCAL_SESSIONS_DIR = Path(__file__).parent / "storage" / "sessions"
LOCAL_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# ── GCS setup ─────────────────────────────────────────────────────────────────

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
_bucket = None

if GCS_BUCKET_NAME:
    from google.cloud import storage as gcs_storage
    _client = gcs_storage.Client()
    _bucket = _client.bucket(GCS_BUCKET_NAME)


def _use_gcs() -> bool:
    return _bucket is not None


# ── Public API ────────────────────────────────────────────────────────────────

def create_session(topic: str, cards: list[dict]) -> str:
    """Persist study session JSON and return the session ID."""
    session_id = str(uuid.uuid4())[:8]
    data = json.dumps({"topic": topic, "cards": cards}, ensure_ascii=False)

    if _use_gcs():
        blob = _bucket.blob(f"sessions/{session_id}.json")
        blob.upload_from_string(data, content_type="application/json")
    else:
        (LOCAL_SESSIONS_DIR / f"{session_id}.json").write_text(data)

    return session_id


def load_session(session_id: str) -> dict | None:
    """Load a session by ID. Returns None if not found."""
    if _use_gcs():
        blob = _bucket.blob(f"sessions/{session_id}.json")
        if not blob.exists():
            return None
        return json.loads(blob.download_as_text())
    else:
        path = LOCAL_SESSIONS_DIR / f"{session_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())


def save_audio(session_id: str, local_path: str):
    """Upload a locally generated MP3 to persistent storage."""
    if _use_gcs():
        blob = _bucket.blob(f"sessions/{session_id}.mp3")
        blob.upload_from_filename(local_path, content_type="audio/mpeg")


def audio_exists(session_id: str) -> bool:
    """Check if the audio file has been generated."""
    if _use_gcs():
        blob = _bucket.blob(f"sessions/{session_id}.mp3")
        return blob.exists()
    else:
        return (LOCAL_SESSIONS_DIR / f"{session_id}.mp3").exists()


def get_audio_path(session_id: str) -> str | None:
    """
    Return a local file path to the audio.
    For GCS, downloads to a temp file first.
    Returns None if audio doesn't exist.
    """
    if _use_gcs():
        blob = _bucket.blob(f"sessions/{session_id}.mp3")
        if not blob.exists():
            return None
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        blob.download_to_filename(tmp.name)
        return tmp.name
    else:
        path = LOCAL_SESSIONS_DIR / f"{session_id}.mp3"
        return str(path) if path.exists() else None


def get_local_audio_path(session_id: str) -> str:
    """Return the local path where audio should be generated."""
    return str(LOCAL_SESSIONS_DIR / f"{session_id}.mp3")
