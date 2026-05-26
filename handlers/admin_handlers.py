"""
Admin Handlers - مدیریت عملیات مدیر
Handler for admin operations
"""

from typing import Any, Tuple
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
    menu += "مدیریت سریع:\n"
    menu += "• 📊 آمار ربات\n"
    menu += "• 🔄 بارگذاری مجدد داده‌ها\n"
    menu += "• 📌 سوالات بی‌پاسخ\n"
    menu += "• 📚 لیست سوال‌وجواب\n"
    menu += "• ➕ افزودن سوال\n"
    menu += "• ➖ حذف سوال\n\n"
    menu += "راهنما:\n"
    menu += "برای پاسخ به تیکت، روی همان پیام <i>Reply</i> بزنید."

    return menu


def _format_avg_response(seconds: float) -> str:
    if seconds <= 0:
        return "-"
    if seconds >= 60:
        return f"{seconds / 60:.1f} دقیقه"
    return f"{seconds:.0f} ثانیه"


async def get_bot_stats(csv_loader: CSVLoader, counters: dict[str, Any]) -> str:
    """
    دریافت آمار ربات
    Get bot statistics
    """
    qa_list = csv_loader.get_all_qa()
    count = len(qa_list)
    bot_answered = int(counters.get("bot_answered", 0))
    admin_answered = int(counters.get("admin_answered", 0))
    unanswered = int(counters.get("unanswered", 0))
    feedback_helpful = int(counters.get("feedback_helpful", 0))
    feedback_unhelpful = int(counters.get("feedback_unhelpful", 0))
    resolved_tickets = int(counters.get("resolved_tickets", 0))
    total_response_seconds = float(counters.get("total_response_seconds", 0.0))
    unanswered_questions = counters.get("unanswered_questions", {}) or {}

    total_answered = bot_answered + admin_answered
    auto_rate = (bot_answered / total_answered * 100.0) if total_answered else 0.0
    avg_response = (total_response_seconds / resolved_tickets) if resolved_tickets else 0.0

    top_unanswered: list[tuple[str, int]] = []
    if isinstance(unanswered_questions, dict):
        cleaned: list[tuple[str, int]] = []
        for question, freq in unanswered_questions.items():
            q = str(question or "").strip()
            if not q:
                continue
            try:
                cleaned.append((q, int(freq)))
            except (TypeError, ValueError):
                continue
        cleaned.sort(key=lambda item: (-item[1], item[0]))
        top_unanswered = cleaned[:5]

    stats = "<b>📊 آمار ربات:</b>\n\n"
    stats += f"1) 📚 تعداد سوال و جواب داخل فایل: {count}\n"
    stats += f"2) 🤖 تعداد پاسخ‌های ربات: {bot_answered}\n"
    stats += f"3) 👨‍💼 تعداد پاسخ‌های ادمین: {admin_answered}\n"
    stats += f"4) ❓ تعداد تیکت‌های باز: {unanswered}\n"
    stats += f"5) ⚡ نرخ پاسخ خودکار: {auto_rate:.1f}%\n"
    stats += f"6) ⏱️ میانگین زمان پاسخ تیکت: {_format_avg_response(avg_response)}\n"
    stats += f"7) 👍 بازخورد مفید: {feedback_helpful}\n"
    stats += f"8) 👎 بازخورد نامفید: {feedback_unhelpful}\n"

    stats += "\n<b>🔥 ۵ سوال پرتکرار بی‌پاسخ (تجمعی):</b>\n"
    if top_unanswered:
        for idx, (question, freq) in enumerate(top_unanswered, start=1):
            stats += f"{idx}) ({freq}) {question}\n"
    else:
        stats += "موردی ثبت نشده است.\n"

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
