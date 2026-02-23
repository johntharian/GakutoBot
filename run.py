#!/usr/bin/env python3
"""
Run the StudyScroll API server and Telegram bot together.

Usage:
    python run.py

Or run them separately:
    uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
    python bot/main.py
"""

import asyncio
import logging
import os
import sys
import threading
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)


def run_api():
    """Run the FastAPI server in a thread."""
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info",
    )


def run_bot():
    """Run the Telegram bot (blocking)."""
    from bot.main import main
    main()


if __name__ == "__main__":
    # Start FastAPI in a background thread
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    # Run bot in the main thread
    run_bot()
