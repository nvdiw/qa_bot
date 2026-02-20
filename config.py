"""
تنظیمات اصلی ربات QABot
Configuration for QABot
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))


def _parse_admin_ids() -> set[int]:
    raw = os.getenv('ADMIN_IDS', '')
    parsed: set[int] = set()
    for item in raw.split(','):
        item = item.strip()
        if not item:
            continue
        try:
            parsed.add(int(item))
        except ValueError:
            continue

    if ADMIN_ID:
        parsed.add(ADMIN_ID)
    return parsed


ADMIN_IDS = _parse_admin_ids()

# File paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
CSV_FILE = DATA_DIR / 'qa_data.csv'
BOT_STATS_FILE = DATA_DIR / 'bot_stats.json'

# CSV Configuration
CSV_QUESTION_COLUMN = 'سوال'  # Change if your CSV has different column name
CSV_ANSWER_COLUMN = 'جواب'    # Change if your CSV has different column name

# Message Configuration
NOT_FOUND_MESSAGE = (
    "متاسفانه پاسخ دقیقی برای این پیام پیدا نکردم. "
    "سوالت برای تیم پشتیبانی ارسال شد و بعد از بررسی بهت جواب می‌دیم."
)
ADMIN_FORWARD_MESSAGE = "سوال جدید از کاربر:"
ANSWER_SENT_MESSAGE = "پاسخ شما ارسال شد!"

# Search Configuration
SIMILARITY_THRESHOLD = 0.6  # Similarity threshold for fuzzy search (0.0 - 1.0)
