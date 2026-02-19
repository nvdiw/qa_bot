"""
QABot - ربات پاسخ دهی سوالات خودکار
Automated Q&A Telegram Bot

استفاده:
1. ابتدا فایل .env را ایجاد کنید
2. BOT_TOKEN و ADMIN_ID را در .env وارد کنید
3. python main.py را اجرا کنید
"""

import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

from config import (
    BOT_TOKEN,
    ADMIN_ID,
    CSV_FILE,
    CSV_QUESTION_COLUMN,
    CSV_ANSWER_COLUMN,
    SIMILARITY_THRESHOLD,
    NOT_FOUND_MESSAGE,
)
from utils import CSVLoader
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

USER_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [["/start", "/help"]],
    resize_keyboard=True,
)

ADMIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["/start", "/help"],
        ["/stats", "/reload"],
        ["/list"],
        ["➕ افزودن سوال", "➖ حذف سوال"],
    ],
    resize_keyboard=True,
)


# ==================== Command Handlers ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command
    """
    user = update.effective_user
    is_admin = user.id == ADMIN_ID
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
        reply_markup=ADMIN_MENU_KEYBOARD if update.effective_user.id == ADMIN_ID else USER_MENU_KEYBOARD,
    )


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display admin menu (only for admin)
    """
    if update.effective_user.id != ADMIN_ID:
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
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ فقط مدیر می تواند از این دستور استفاده کند.")
        return

    stats_msg = await get_bot_stats(csv_loader)
    await update.message.reply_text(
        stats_msg,
        parse_mode=ParseMode.HTML,
        reply_markup=ADMIN_MENU_KEYBOARD,
    )


async def list_qa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    List all Q&A (only for admin)
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ فقط مدیر می تواند از این دستور استفاده کند.")
        return

    list_msg = await list_all_qa(csv_loader)
    await update.message.reply_text(
        list_msg,
        parse_mode=ParseMode.HTML,
        reply_markup=ADMIN_MENU_KEYBOARD,
    )


async def reload_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Reload CSV file (only for admin)
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ فقط مدیر می تواند از این دستور استفاده کند.")
        return

    csv_loader.reload_csv()
    await update.message.reply_text(
        "✅ فایل CSV بارگذاری مجدد شد.",
        reply_markup=ADMIN_MENU_KEYBOARD,
    )


# ==================== Message Handlers ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle user messages
    """
    user = update.effective_user
    question = update.message.text

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
        # Send answer to user
        await update.message.reply_text(
            response,
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"Answer sent to user {user.id}")

    else:
        # Send to admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=response,
            parse_mode=ParseMode.HTML,
            reply_markup=None,
        )

        # Inform user
        await update.message.reply_text(
            NOT_FOUND_MESSAGE,
            parse_mode=ParseMode.HTML,
        )

        # Store user_id and question in context for admin's reply
        context.user_data['last_user_id'] = user.id
        context.user_data['last_question'] = question


async def handle_admin_message_reply(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle admin's reply to unanswered questions
    """
    if update.effective_user.id != ADMIN_ID:
        return

    reply_text = (update.message.text or "").strip()
    original_msg = update.message.reply_to_message.text if update.message.reply_to_message else ""
    admin_action = context.user_data.get("admin_action")

    # Start add flow
    if reply_text == "➕ افزودن سوال":
        context.user_data["admin_action"] = "await_add_question"
        context.user_data.pop("pending_question", None)
        await update.message.reply_text(
            "لطفا متن سوال جدید را ارسال کنید.",
            reply_markup=ADMIN_MENU_KEYBOARD,
        )
        return

    # Start delete flow
    if reply_text == "➖ حذف سوال":
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

    # Extract user_id and question from the original message
    try:
        lines = original_msg.split('\n')
        user_id_line = [l for l in lines if 'ID:' in l][0]
        user_id = int(user_id_line.split('>')[1].split('<')[0])

        question = context.user_data.get('last_question', '')

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

    if not ADMIN_ID:
        logger.error("❌ ADMIN_ID مشخص نشده! لطفا فایل .env را بررسی کنید.")
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

    # Handle admin replies
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Chat(ADMIN_ID),
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
    logger.info(f"🔒 Admin ID: {ADMIN_ID}")

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
