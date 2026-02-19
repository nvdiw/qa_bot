"""
Admin Handlers - مدیریت عملیات مدیر
Handler for admin operations
"""

from typing import Tuple
from utils import CSVLoader


async def handle_admin_reply(
    reply_text: str,
    original_question: str,
    user_id: int,
    csv_loader: CSVLoader
) -> Tuple[bool, str]:
    """
    مدیریت پاسخ مدیر و افزودن به پایگاه داده
    Handle admin reply and add to database
    """
    try:
        success = csv_loader.add_qa(original_question, reply_text)

        if success:
            msg = f"✅ جواب برای سوال کاربر ID {user_id} ثبت شد.\n"
            msg += f"📝 سوال: {original_question}\n"
            msg += f"💬 جواب: {reply_text}"
            return True, msg

        return False, "❌ خطا در ثبت جواب"

    except Exception as e:
        return False, f"❌ خطا: {str(e)}"


def create_admin_menu() -> str:
    """
    ایجاد منوی مدیر
    Create admin menu
    """
    menu = "<b>🔐 منوی مدیر</b>\n\n"
    menu += "دستورات موجود:\n"
    menu += "/stats - نمایش آمار\n"
    menu += "/reload - بارگذاری دوباره CSV\n"
    menu += "/list - نمایش تمام سوالات\n\n"
    menu += "گزینه های دکمه ای:\n"
    menu += "➕ افزودن سوال - افزودن سوال و جواب جدید\n"
    menu += "➖ حذف سوال - حذف یک سوال از CSV\n\n"
    menu += "<i>برای پاسخ دادن به سوال، روی پیام Reply کنید.</i>"

    return menu


async def get_bot_stats(csv_loader: CSVLoader) -> str:
    """
    دریافت آمار ربات
    Get bot statistics
    """
    qa_list = csv_loader.get_all_qa()
    count = len(qa_list)

    stats = "<b>📊 آمار ربات:</b>\n\n"
    stats += f"📚 تعداد سوالات: {count}\n"

    return stats


async def list_all_qa(csv_loader: CSVLoader, page: int = 1, per_page: int = 5) -> str:
    """
    نمایش تمام سوالات و جوابات
    List all Q&A pairs with pagination
    """
    qa_list = csv_loader.get_all_qa()

    if not qa_list:
        return "❌ هیچ سوالی ثبت نشده است."

    total = len(qa_list)
    total_pages = (total + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    page_items = qa_list[start_idx:end_idx]

    msg = f"<b>📚 لیست سوالات و جوابات</b> (صفحه {page}/{total_pages})\n\n"

    for i, (question, answer) in enumerate(page_items, start=start_idx + 1):
        msg += f"<b>{i}. {question}</b>\n"
        msg += f"👉 {answer}\n\n"

    return msg
