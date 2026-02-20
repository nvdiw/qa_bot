"""
Message Helper - کمک کننده برای قالب بندی پیام ها
Helper functions for message formatting
"""

import re
from typing import Optional, List, Tuple


_GREETINGS = ("سلام", "درود", "خوبی", "خوبین", "صبح بخیر", "شب بخیر", "وقت بخیر", "hello", "hi")


def _is_greeting_message(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return any(g in normalized for g in _GREETINGS)


def _dedupe_answers(results: List[Tuple[str, float]]) -> List[str]:
    unique = []
    seen = set()
    for answer, _ in results:
        key = (answer or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(key)
    return unique


def _is_greeting_answer(answer: str) -> bool:
    text = (answer or "").strip()
    return ("سلام" in text) or ("خوش آمد" in text) or ("خوش‌آمد" in text)


def format_answer(answer: str, similarity: Optional[float] = None) -> str:
    """
    قالب بندی جواب برای ارسال به کاربر
    Format answer for user
    """
    return format_compact_response("", [(answer, similarity or 1.0)])


def format_compact_response(user_question: str, results: List[Tuple[str, float]]) -> str:
    """
    یک پاسخ یکپارچه و مکالمه‌ای برای کاربر می‌سازد.
    """
    answers = _dedupe_answers(results)
    if not answers:
        return ""

    greet_line = "سلام، خوشحال می‌شم کمک کنم.\n\n" if _is_greeting_message(user_question) else ""
    if greet_line:
        non_greeting_answers = [a for a in answers if not _is_greeting_answer(a)]
        if non_greeting_answers:
            answers = non_greeting_answers
        elif len(answers) == 1:
            return "سلام، خوشحال می‌شم کمک کنم.\n\nچطور می‌تونم کمکت کنم؟"

    if len(answers) == 1:
        body = f"✅ {answers[0]}"
    else:
        body = "✅ پاسخ کامل سوالت:\n"
        body += "\n".join([f"• {ans}" for ans in answers])

    footer = "\n\nاگر خواستی با جزئیات بیشتر هم توضیح می‌دم."
    return f"{greet_line}{body}{footer}"


def escape_markdown(text: str) -> str:
    """
    Escape special markdown characters
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def create_user_info_message(user_id: int, username: Optional[str], first_name: Optional[str], question: str) -> str:
    """
    ایجاد پیام اطلاعات کاربر برای مدیر
    Create user info message for admin
    """
    user_info = "👤 <b>کاربر جدید:</b>\n"
    user_info += f"ID: <code>{user_id}</code>\n"

    if username:
        user_info += f"Username: @{username}\n"
    if first_name:
        user_info += f"نام: {first_name}\n"

    user_info += f"\n❓ <b>سوال:</b>\n{question}"

    return user_info


def create_unanswered_message(question: str, user_id: int) -> str:
    """
    پیام سوال بدون جواب برای مدیر
    Create unanswered question message for admin
    """
    msg = f"❓ <b>سوال بدون جواب:</b>\n\n{question}\n\n"
    msg += f"<i>از کاربر ID: {user_id}</i>\n\n"
    msg += "<i>برای پاسخ دادن، روی این پیام Reply کنید.</i>"

    return msg
