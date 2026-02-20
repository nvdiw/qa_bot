"""
Admin Handlers - مدیریت عملیات مدیر
Handler for admin operations
"""

from typing import Tuple, Dict
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
    menu = "<b>🔐 پنل مدیریت ربات</b>\n\n"
    menu += "<b>گزینه‌های اصلی:</b>\n"
    menu += "• آمار ربات\n"
    menu += "• بارگذاری مجدد داده‌ها\n"
    menu += "• سوالات بی‌پاسخ\n"
    menu += "• لیست سوال‌وجواب\n"
    menu += "• افزودن سوال\n"
    menu += "• حذف سوال\n\n"
    menu += "<b>میانبرهای کیبورد:</b>\n"
    menu += "• 📌 سوالات بی پاسخ\n"
    menu += "• ➕ افزودن سوال | ➖ حذف سوال\n\n"
    menu += "<b>نکته:</b>\n"
    menu += "برای پاسخ به تیکت کاربر، روی همان پیام <i>پاسخ</i> بزنید."

    return menu


async def get_bot_stats(csv_loader: CSVLoader, counters: Dict[str, int]) -> str:
    """
    دریافت آمار ربات
    Get bot statistics
    """
    qa_list = csv_loader.get_all_qa()
    count = len(qa_list)
    bot_answered = int(counters.get("bot_answered", 0))
    admin_answered = int(counters.get("admin_answered", 0))
    unanswered = int(counters.get("unanswered", 0))

    stats = "<b>📊 آمار ربات:</b>\n\n"
    stats += f"1) 📚 تعداد سوال و جواب داخل فایل: {count}\n"
    stats += f"2) 🤖 تعداد سوال‌های پاسخ داده‌شده توسط ربات: {bot_answered}\n"
    stats += f"3) 👨‍💼 تعداد سوال‌های پاسخ داده‌شده توسط ادمین: {admin_answered}\n"
    stats += f"4) ❓ تعداد سوال‌های پاسخ داده‌نشده: {unanswered}\n"

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
