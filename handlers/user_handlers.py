"""
User Handlers - مدیریت پیام های کاربران
Handler for user messages
"""

from typing import Tuple, Optional
from utils import CSVLoader, format_answer
from utils.message_helper import create_user_info_message


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
    result = csv_loader.search(question)

    if result:
        answer, similarity = result
        response = format_answer(answer, similarity)
        return response, True

    user_info = create_user_info_message(user_id, username, first_name, question)
    return user_info, False


async def handle_start_command(user_id: int, first_name: Optional[str] = None) -> str:
    """
    مدیریت دستور /start
    Handle /start command
    """
    name = first_name if first_name else "دوست"
    welcome_msg = f"سلام {name}! 👋\n\n"
    welcome_msg += "خوش آمدید به ربات پاسخ دهی سوالات! 🤖\n\n"
    welcome_msg += "لطفا سوال خود را بپرسید و من سعی می کنم جواب بدهم.\n"
    welcome_msg += "اگر جوابی نتوانستم بدهم، سوال برای مدیر ارسال خواهد شد."

    return welcome_msg


async def handle_help_command() -> str:
    """
    مدیریت دستور /help
    Handle /help command
    """
    help_msg = "<b>راهنما:</b>\n\n"
    help_msg += "🤖 <b>چگونه از ربات استفاده کنم؟</b>\n\n"
    help_msg += "1️⃣ سوال خود را بپرسید\n"
    help_msg += "2️⃣ ربات سعی می کند جواب دهد\n"
    help_msg += "3️⃣ اگر جوابی موجود نباشد، سوال به مدیر منتقل می شود\n"
    help_msg += "4️⃣ وقتی مدیر جواب بدهد، شما آن را دریافت می کنید\n\n"
    help_msg += "<b>دستورات:</b>\n"
    help_msg += "/start - شروع\n"
    help_msg += "/help - راهنما\n"

    return help_msg