"""
Message Helper - کمک کننده برای قالب بندی پیام ها
Helper functions for message formatting
"""

from typing import Optional


def format_answer(answer: str, similarity: Optional[float] = None) -> str:
    """
    قالب بندی جواب برای ارسال به کاربر
    Format answer for user
    """
    formatted = f"📌 <b>جواب:</b>\n{answer}"

    if similarity and similarity < 1.0:
        confidence = int(similarity * 100)
        formatted += f"\n\n<i>میزان دقت: {confidence}%</i>"

    return formatted


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