"""
QABot - ربات پاسخ دهی سوالات خودکار
Automated Q&A Telegram Bot

استفاده:
1. ابتدا فایل .env را ایجاد کنید
2. BOT_TOKEN و ADMIN_ID (یا ADMIN_IDS) را در .env وارد کنید
3. python main.py را اجرا کنید
"""

import logging
import re
from itertools import count
from typing import Dict, Any
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    CSV_FILE,
    BOT_STATS_FILE,
    CSV_QUESTION_COLUMN,
    CSV_ANSWER_COLUMN,
    SIMILARITY_THRESHOLD,
    NOT_FOUND_MESSAGE,
)
from utils import CSVLoader
from utils.stats_store import BotStatsStore
from handlers import handle_user_message, handle_admin_reply
from handlers.admin_handlers import (
    create_admin_menu,
    get_bot_stats,
    list_all_qa,
)
from handlers.user_handlers import handle_start_command, handle_help_command

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Initialize CSV Loader
csv_loader = CSVLoader(
    csv_file=CSV_FILE,
    question_col=CSV_QUESTION_COLUMN,
    answer_col=CSV_ANSWER_COLUMN,
    similarity_threshold=SIMILARITY_THRESHOLD,
)
bot_stats = BotStatsStore(BOT_STATS_FILE)

USER_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["شروع", "راهنما"],
        ["نمونه سوال"],
    ],
    resize_keyboard=True,
)

ADMIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["شروع", "راهنما"],
        ["آمار ربات", "بارگذاری مجدد"],
        ["سوالات بی‌پاسخ", "لیست سوال‌وجواب"],
        ["📌 سوالات بی پاسخ"],
        ["➕ افزودن سوال", "➖ حذف سوال"],
    ],
    resize_keyboard=True,
)

pending_questions: Dict[int, Dict[str, Any]] = {}
pending_ticket_counter = count(1)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _admin_ids() -> list[int]:
    return sorted(ADMIN_IDS)


def _build_list_pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup | None:
    if total_pages <= 1:
        return None

    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅️ صفحه قبل", callback_data=f"list:{page - 1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("صفحه بعد ➡️", callback_data=f"list:{page + 1}"))
    if not buttons:
        return None
    return InlineKeyboardMarkup([buttons])


def _build_pending_pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup | None:
    if total_pages <= 1:
        return None
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅️ ۵ مورد قبل", callback_data=f"pending:{page - 1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("۵ مورد بعد ➡️", callback_data=f"pending:{page + 1}"))
    if not buttons:
        return None
    return InlineKeyboardMarkup([buttons])


def _track_ticket_message(ticket_id: int, admin_id: int, message_id: int) -> None:
    ticket = pending_questions.get(ticket_id)
    if not ticket:
        return
    mapping = ticket.setdefault("admin_message_ids", {})
    ids = mapping.setdefault(admin_id, [])
    if message_id not in ids:
        ids.append(message_id)


async def _delete_ticket_messages_from_other_admins(
    context: ContextTypes.DEFAULT_TYPE,
    ticket: Dict[str, Any],
    answered_admin_id: int,
) -> None:
    mapping = ticket.get("admin_message_ids", {})
    for admin_id, message_ids in mapping.items():
        if admin_id == answered_admin_id:
            continue
        for message_id in list(message_ids):
            try:
                await context.bot.delete_message(chat_id=admin_id, message_id=message_id)
            except Exception:
                continue


def _build_pending_message(ticket_id: int, user_id: int, username: str, first_name: str, question: str) -> str:
    username_line = f"Username: @{username}" if username else "Username: -"
    name_line = f"نام: {first_name}" if first_name else "نام: -"
    msg = "👤 <b>کاربر جدید:</b>\n"
    msg += f"ID: {user_id}\n"
    msg += f"{username_line}\n"
    msg += f"{name_line}\n"
    msg += f"🎫 Ticket: {ticket_id}\n\n"
    msg += f"❓ <b>سوال:</b>\n{question}\n\n"
    msg += "<i>برای پاسخ دادن، روی همین پیام ریپلای کنید.</i>"
    return msg


def _extract_ticket_id(reply_message_text: str) -> int | None:
    if not reply_message_text:
        return None
    match = re.search(r"Ticket:\s*(\d+)", reply_message_text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _extract_user_id(reply_message_text: str) -> int | None:
    if not reply_message_text:
        return None
    match = re.search(r"ID:\s*(?:<code>)?(\d+)(?:</code>)?", reply_message_text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _extract_question(reply_message_text: str) -> str:
    if not reply_message_text:
        return ""
    if "❓" in reply_message_text and "سوال" in reply_message_text:
        parts = re.split(r"❓\s*<b>سوال:</b>|❓\s*سوال:", reply_message_text, maxsplit=1)
        if len(parts) == 2:
            return parts[1].strip()
    return ""


async def send_pending_questions_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("❌ فقط مدیر می تواند از این دستور استفاده کند.")
        return

    if not pending_questions:
        await update.message.reply_text(
            "✅ در حال حاضر سوال بی پاسخی وجود ندارد.",
            reply_markup=ADMIN_MENU_KEYBOARD,
        )
        return

    page = 1
    page_size = 5
    ticket_ids = sorted(pending_questions.keys())
    total = len(ticket_ids)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page_ids = ticket_ids[(page - 1) * page_size: page * page_size]

    await update.message.reply_text(
        f"📌 سوالات بی‌پاسخ: {total}\n"
        f"نمایش {len(page_ids)} مورد (صفحه {page}/{total_pages})\n"
        "برای پاسخ دادن، روی پیام تیکت ریپلای کنید.",
        reply_markup=_build_pending_pagination_keyboard(page, total_pages),
    )

    for ticket_id in page_ids:
        item = pending_questions[ticket_id]
        sent = await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=_build_pending_message(
                ticket_id=ticket_id,
                user_id=item["user_id"],
                username=item.get("username"),
                first_name=item.get("first_name"),
                question=item["question"],
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=None,
        )
        _track_ticket_message(ticket_id, update.effective_user.id, sent.message_id)


# ==================== Command Handlers ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command
    """
    user = update.effective_user
    is_admin = _is_admin(user.id)
    welcome_msg = await handle_start_command(user.id, user.first_name)
    if is_admin:
        welcome_msg += "\n\n" + create_admin_menu()

    await update.message.reply_text(
        welcome_msg,
        parse_mode=ParseMode.HTML,
        reply_markup=ADMIN_MENU_KEYBOARD if is_admin else USER_MENU_KEYBOARD,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command
    """
    help_msg = await handle_help_command()
    await update.message.reply_text(
        help_msg,
        parse_mode=ParseMode.HTML,
        reply_markup=ADMIN_MENU_KEYBOARD if _is_admin(update.effective_user.id) else USER_MENU_KEYBOARD,
    )


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display admin menu (only for admin)
    """
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("❌ فقط مدیر می تواند از این دستور استفاده کند.")
        return

    menu = create_admin_menu()
    await update.message.reply_text(
        menu,
        parse_mode=ParseMode.HTML,
        reply_markup=ADMIN_MENU_KEYBOARD,
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show bot statistics (only for admin)
    """
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("❌ فقط مدیر می تواند از این دستور استفاده کند.")
        return

    stats_msg = await get_bot_stats(csv_loader, bot_stats.snapshot())
    await update.message.reply_text(
        stats_msg,
        parse_mode=ParseMode.HTML,
        reply_markup=ADMIN_MENU_KEYBOARD,
    )


async def list_qa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    List all Q&A (only for admin)
    """
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("❌ فقط مدیر می تواند از این دستور استفاده کند.")
        return

    page = 1
    if context.args:
        try:
            page = int(context.args[0])
        except ValueError:
            await update.message.reply_text(
                "❌ شماره صفحه نامعتبر است.",
                reply_markup=ADMIN_MENU_KEYBOARD,
            )
            return

    qa_count = len(csv_loader.get_all_qa())
    total_pages = max(1, (qa_count + 5 - 1) // 5)
    page = max(1, min(page, total_pages))
    context.user_data["list_page"] = page

    list_msg = await list_all_qa(csv_loader, page=page, per_page=5)
    nav_markup = _build_list_pagination_keyboard(page, total_pages)

    await update.message.reply_text(
        list_msg,
        parse_mode=ParseMode.HTML,
        reply_markup=nav_markup,
    )


async def reload_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Reload CSV file (only for admin)
    """
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("❌ فقط مدیر می تواند از این دستور استفاده کند.")
        return

    csv_loader.reload_csv()
    await update.message.reply_text(
        "✅ فایل CSV بارگذاری مجدد شد.",
        reply_markup=ADMIN_MENU_KEYBOARD,
    )


async def pending_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show unanswered questions (only for admin)
    """
    await send_pending_questions_list(update, context)


async def handle_list_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    await query.answer()

    user_id = query.from_user.id
    if not _is_admin(user_id):
        await query.answer("شما دسترسی ندارید.", show_alert=True)
        return

    data = query.data or ""
    if not (data.startswith("list:") or data.startswith("pending:")):
        return

    try:
        page = int(data.split(":", maxsplit=1)[1])
    except ValueError:
        return

    if data.startswith("list:"):
        qa_count = len(csv_loader.get_all_qa())
        total_pages = max(1, (qa_count + 5 - 1) // 5)
        page = max(1, min(page, total_pages))

        list_msg = await list_all_qa(csv_loader, page=page, per_page=5)
        nav_markup = _build_list_pagination_keyboard(page, total_pages)

        await query.edit_message_text(
            text=list_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=nav_markup,
        )
        return

    # pending pagination
    page_size = 5
    ticket_ids = sorted(pending_questions.keys())
    total = len(ticket_ids)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    page_ids = ticket_ids[(page - 1) * page_size: page * page_size]

    await query.edit_message_text(
        text=(
            f"📌 سوالات بی‌پاسخ: {total}\n"
            f"نمایش {len(page_ids)} مورد (صفحه {page}/{total_pages})\n"
            "برای پاسخ دادن، روی پیام تیکت ریپلای کنید."
        ),
        reply_markup=_build_pending_pagination_keyboard(page, total_pages),
    )

    for ticket_id in page_ids:
        item = pending_questions[ticket_id]
        sent = await context.bot.send_message(
            chat_id=user_id,
            text=_build_pending_message(
                ticket_id=ticket_id,
                user_id=item["user_id"],
                username=item.get("username"),
                first_name=item.get("first_name"),
                question=item["question"],
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=None,
        )
        _track_ticket_message(ticket_id, user_id, sent.message_id)


# ==================== Message Handlers ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle user messages
    """
    user = update.effective_user
    question = (update.message.text or "").strip()

    if question in {"شروع", "/start"}:
        await start(update, context)
        return

    if question in {"راهنما", "/help"}:
        help_msg = await handle_help_command()
        await update.message.reply_text(
            help_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=ADMIN_MENU_KEYBOARD if _is_admin(user.id) else USER_MENU_KEYBOARD,
        )
        return

    if question == "نمونه سوال":
        sample_msg = (
            "چند نمونه خوب برای تست:\n\n"
            "• قیمت اشتراک چقدره؟\n"
            "• ساعات کاری شما چیه؟\n"
            "• سلام، لطفا قیمت و نحوه ثبت‌نام رو می‌گید؟"
        )
        await update.message.reply_text(
            sample_msg,
            reply_markup=ADMIN_MENU_KEYBOARD if _is_admin(user.id) else USER_MENU_KEYBOARD,
        )
        return

    logger.info(f"Message from {user.id} ({user.first_name}): {question}")

    # Show typing indicator
    await update.message.chat.send_action("typing")

    # Handle user message
    response, is_answered = await handle_user_message(
        question=question,
        user_id=user.id,
        csv_loader=csv_loader,
        username=user.username,
        first_name=user.first_name,
    )

    if is_answered:
        bot_stats.increment_bot_answered()
        # Send answer to user
        await update.message.reply_text(
            response,
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"Answer sent to user {user.id}")

    else:
        # Do not forward admin's own unmatched questions back to admin queue.
        if _is_admin(user.id):
            await update.message.reply_text(
                "پاسخی با این سوال پیدا نشد.",
                reply_markup=ADMIN_MENU_KEYBOARD,
            )
            return

        ticket_id = next(pending_ticket_counter)
        pending_questions[ticket_id] = {
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "question": question,
            "admin_message_ids": {},
        }
        bot_stats.increment_unanswered()

        admin_msg = _build_pending_message(
            ticket_id=ticket_id,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            question=question,
        )

        # Send to all admins
        for admin_id in _admin_ids():
            sent = await context.bot.send_message(
                chat_id=admin_id,
                text=admin_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=None,
            )
            _track_ticket_message(ticket_id, admin_id, sent.message_id)

        # Inform user
        await update.message.reply_text(
            NOT_FOUND_MESSAGE,
            parse_mode=ParseMode.HTML,
        )

        logger.info(f"Unanswered question queued as ticket {ticket_id} for user {user.id}")


async def handle_admin_message_reply(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle admin's reply to unanswered questions
    """
    if not _is_admin(update.effective_user.id):
        return

    reply_text = (update.message.text or "").strip()
    original_msg = update.message.reply_to_message.text if update.message.reply_to_message else ""
    admin_action = context.user_data.get("admin_action")

    if reply_text in {"شروع", "/start"}:
        await start(update, context)
        return

    if reply_text in {"راهنما", "/help"}:
        await help_command(update, context)
        return

    if reply_text in {"آمار ربات", "/stats"}:
        await stats(update, context)
        return

    if reply_text in {"بارگذاری مجدد", "/reload"}:
        await reload_csv(update, context)
        return

    if reply_text in {"سوالات بی‌پاسخ", "📌 سوالات بی پاسخ", "/pending"}:
        await send_pending_questions_list(update, context)
        return

    if reply_text in {"لیست سوال‌وجواب", "/list"}:
        qa_count = len(csv_loader.get_all_qa())
        total_pages = max(1, (qa_count + 5 - 1) // 5)
        page = 1
        context.user_data["list_page"] = page
        list_msg = await list_all_qa(csv_loader, page=page, per_page=5)
        nav_markup = _build_list_pagination_keyboard(page, total_pages)
        await update.message.reply_text(
            list_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=nav_markup,
        )
        return

    # Start add flow
    if reply_text in {"➕ افزودن سوال", "افزودن سوال"}:
        context.user_data["admin_action"] = "await_add_question"
        context.user_data.pop("pending_question", None)
        await update.message.reply_text(
            "لطفا متن سوال جدید را ارسال کنید.",
            reply_markup=ADMIN_MENU_KEYBOARD,
        )
        return

    # Start delete flow
    if reply_text in {"➖ حذف سوال", "حذف سوال"}:
        context.user_data["admin_action"] = "await_delete_question"
        await update.message.reply_text(
            "لطفا متن دقیق سوالی که باید حذف شود را ارسال کنید.",
            reply_markup=ADMIN_MENU_KEYBOARD,
        )
        return

    # Continue add flow
    if admin_action == "await_add_question":
        context.user_data["pending_question"] = reply_text
        context.user_data["admin_action"] = "await_add_answer"
        await update.message.reply_text(
            "سوال ثبت شد. حالا لطفا جواب این سوال را ارسال کنید.",
            reply_markup=ADMIN_MENU_KEYBOARD,
        )
        return

    if admin_action == "await_add_answer":
        pending_question = context.user_data.get("pending_question", "").strip()
        if not pending_question:
            context.user_data.pop("admin_action", None)
            await update.message.reply_text(
                "❌ سوال پیدا نشد. دوباره از «➕ افزودن سوال» شروع کنید.",
                reply_markup=ADMIN_MENU_KEYBOARD,
            )
            return

        if csv_loader.add_qa(pending_question, reply_text):
            await update.message.reply_text(
                "✅ سوال و جواب جدید با موفقیت اضافه شد.",
                reply_markup=ADMIN_MENU_KEYBOARD,
            )
        else:
            await update.message.reply_text(
                "❌ خطا در ذخیره سوال و جواب.",
                reply_markup=ADMIN_MENU_KEYBOARD,
            )

        context.user_data.pop("admin_action", None)
        context.user_data.pop("pending_question", None)
        return

    # Continue delete flow
    if admin_action == "await_delete_question":
        if csv_loader.remove_qa(reply_text):
            await update.message.reply_text(
                "✅ سوال موردنظر حذف شد.",
                reply_markup=ADMIN_MENU_KEYBOARD,
            )
        else:
            await update.message.reply_text(
                "❌ سوالی با این متن پیدا نشد.",
                reply_markup=ADMIN_MENU_KEYBOARD,
            )
        context.user_data.pop("admin_action", None)
        return

    # If this is not a reply and no admin workflow is active, treat admin like a normal user question.
    if not update.message.reply_to_message:
        await handle_message(update, context)
        return

    # Extract ticket data from the original message
    try:
        ticket_id = _extract_ticket_id(original_msg)
        ticket = None
        if ticket_id is not None:
            ticket = pending_questions.get(ticket_id)
            if not ticket:
                await update.message.reply_text(
                    "❌ این تیکت پیدا نشد یا قبلا پاسخ داده شده است.",
                    reply_markup=ADMIN_MENU_KEYBOARD,
                )
                return
            user_id = ticket["user_id"]
            question = ticket["question"]
        else:
            # Fallback for older forwarded messages without Ticket.
            user_id = _extract_user_id(original_msg)
            question = _extract_question(original_msg)
            if user_id is None:
                await update.message.reply_text(
                    "❌ این پیام قابل شناسایی نیست. لطفا روی پیام سوال کاربر ریپلای کنید.",
                    reply_markup=ADMIN_MENU_KEYBOARD,
                )
                return

        logger.info(f"Admin reply: User {user_id}, Answer: {reply_text}")

        # Add to database
        success, msg = await handle_admin_reply(
            reply_text=reply_text,
            original_question=question,
            user_id=user_id,
            csv_loader=csv_loader,
        )

        # Notify admin
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        # Send answer to user
        user_response = f"📌 <b>جواب شما:</b>\n{reply_text}"
        await context.bot.send_message(
            chat_id=user_id,
            text=user_response,
            parse_mode=ParseMode.HTML,
        )

        if ticket_id is not None:
            if ticket:
                await _delete_ticket_messages_from_other_admins(
                    context=context,
                    ticket=ticket,
                    answered_admin_id=update.effective_user.id,
                )
            if success:
                bot_stats.increment_admin_answered()
                bot_stats.decrement_unanswered()
            pending_questions.pop(ticket_id, None)
            await update.message.reply_text(
                f"✅ تیکت {ticket_id} از لیست سوالات بی پاسخ خارج شد.",
                reply_markup=ADMIN_MENU_KEYBOARD,
            )

            if len(_admin_ids()) > 1:
                for admin_id in _admin_ids():
                    if admin_id == update.effective_user.id:
                        continue
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"✅ تیکت {ticket_id} توسط ادمین {update.effective_user.id} پاسخ داده شد و بسته شد.",
                    )

        logger.info(f"Answer sent to user {user_id}")

    except Exception as e:
        logger.error(f"Error handling admin reply: {e}")
        await update.message.reply_text(f"❌ خطا: {str(e)}")


# ==================== Main Application ====================

def main() -> None:
    """
    Start the bot
    """
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN مشخص نشده! لطفا فایل .env را بررسی کنید.")
        return

    if not ADMIN_IDS:
        logger.error("❌ ADMIN_ID/ADMIN_IDS مشخص نشده! لطفا فایل .env را بررسی کنید.")
        return

    logger.info("🤖 شروع ربات QABot...")

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_menu))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("list", list_qa))
    application.add_handler(CommandHandler("reload", reload_csv))
    application.add_handler(CommandHandler("pending", pending_list))
    application.add_handler(CallbackQueryHandler(handle_list_pagination, pattern=r"^(list|pending):\d+$"))

    # Handle admin replies
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.User(user_id=_admin_ids()),
            handle_admin_message_reply,
        )
    )

    # Handle user messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    logger.info("✅ ربات آماده است!")
    logger.info(f"🔒 Admin IDs: {_admin_ids()}")

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
