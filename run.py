#!/usr/bin/env python3
"""
Run the StudyScroll server.

The FastAPI server handles everything:
  - Telegram bot (via webhook)
  - Session API
  - Mini App static files

Usage:
    python run.py
"""

import logging
import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)

if __name__ == "__main__":
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info",
    )
