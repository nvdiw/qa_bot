"""
User Handlers - مدیریت پیام های کاربران
Handler for user messages
"""

import re
from typing import Tuple, Optional
from utils import CSVLoader
from utils.message_helper import create_user_info_message, format_compact_response


async def handle_user_message(
    question: str,
    user_id: int,
    csv_loader: CSVLoader,
    username: Optional[str] = None,
    first_name: Optional[str] = None
) -> Tuple[Optional[str], bool]:
    """
    مدیریت پیام کاربر و جستجو در پایگاه داده
    Handle user message and search in Q&A database

    Args:
        question: User's question
        user_id: User's telegram ID
        csv_loader: CSV loader instance
        username: User's username
        first_name: User's first name

    Returns:
        Tuple of (response_message, is_answered)
        - If question is answered: (answer_text, True)
        - If not answered: (admin_notification, False)
    """
    results = csv_loader.search_many(question, max_answers=2)
    refined_question = _strip_smalltalk_prefix(question)
    if refined_question and refined_question != question:
        refined_results = csv_loader.search_many(refined_question, max_answers=2)
        results = _merge_results(results, refined_results, limit=2)

    if refined_question and _is_greeting_only_result(results):
        for token in _extract_focus_tokens(refined_question):
            token_results = csv_loader.search_many(token, max_answers=1)
            results = _merge_results(results, token_results, limit=2)

    if results:
        response = format_compact_response(question, results)
        return response, True

    user_info = create_user_info_message(user_id, username, first_name, question)
    return user_info, False


async def handle_start_command(user_id: int, first_name: Optional[str] = None) -> str:
    """
    مدیریت دستور /start
    Handle /start command
    """
    name = first_name if first_name else "دوست"
    welcome_msg = f"سلام {name} 🌟\n\n"
    welcome_msg += "به ربات پشتیبانی خوش اومدی.\n"
    welcome_msg += "سوالت رو بپرس تا جواب مناسب رو پیدا کنم.\n\n"
    welcome_msg += "<b>چطور استفاده کنی؟</b>\n"
    welcome_msg += "1) سوالت رو بفرست\n"
    welcome_msg += "2) جواب رو دریافت کن\n"
    welcome_msg += "3) اگر جواب آماده نباشه، برای ادمین ارسال می‌شه\n\n"
    welcome_msg += "<b>نمونه سوال:</b>\n"
    welcome_msg += "• قیمت اشتراک چقدره؟\n"
    welcome_msg += "• ساعات کاری و نحوه ثبت‌نام رو می‌گید؟"

    return welcome_msg


async def handle_help_command() -> str:
    """
    مدیریت دستور /help
    Handle /help command
    """
    help_msg = "<b>راهنمای سریع</b>\n\n"
    help_msg += "• سوالت رو ساده و واضح بپرس.\n"
    help_msg += "• جواب‌ها از بانک سوال‌وجواب ربات پیدا می‌شن.\n"
    help_msg += "• اگر جواب آماده نباشه، سوالت مستقیم برای ادمین میره.\n\n"
    help_msg += "<b>دستورات:</b>\n"
    help_msg += "شروع - نمایش پیام شروع\n"
    help_msg += "راهنما - نمایش راهنما\n\n"
    help_msg += "همین الان سوالت رو بفرست ✅"

    return help_msg


def _strip_smalltalk_prefix(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(
        r"^\s*(سلام|درود|خوبی|خوبین|صبح بخیر|شب بخیر|وقت بخیر)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\b(لطفا|لطفاً|ممنون|مرسی|میشه|میشود|میکنید|می‌کنید)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ،,.؟?!")
    return cleaned


def _merge_results(primary: list[tuple[str, float]], secondary: list[tuple[str, float]], limit: int = 2) -> list[tuple[str, float]]:
    merged: list[tuple[str, float]] = []
    seen = set()
    for answer, score in (primary + secondary):
        key = (answer or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append((answer, score))
        if len(merged) >= limit:
            break
    return merged


def _is_greeting_only_result(results: list[tuple[str, float]]) -> bool:
    if not results:
        return False
    return all(
        ("سلام" in (answer or "")) or ("خوش آمد" in (answer or "")) or ("خوش‌آمد" in (answer or ""))
        for answer, _ in results
    )


def _extract_focus_tokens(text: str) -> list[str]:
    tokens = [tok for tok in re.split(r"\s+", (text or "").strip()) if len(tok) >= 3]
    blocked = {"لطفا", "لطفاً", "ممنون", "مرسی", "بگید", "لطف", "میکنید", "می‌کنید"}
    tokens = [t for t in tokens if t not in blocked]
    # Prefer informative tokens first.
    tokens.sort(key=lambda t: (0 if t in {"قیمت", "اشتراک", "هزینه"} else 1, -len(t)))
    return tokens[:3]
