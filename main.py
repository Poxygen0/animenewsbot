import time
import os

# Telegram
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    AIORateLimiter,
    ApplicationBuilder,
    CallbackQueryHandler,
    CallbackContext,
    CommandHandler,
    ConversationHandler,
    Defaults,
    filters,
    MessageHandler,
)
from telegram.warnings import PTBUserWarning
from warnings import filterwarnings


from config import config
# from handlers.command_handlers import ()
# from handlers.conversation_handlers import ()
# from handlers.message_handlers import ()
from utils.helpers import send_critical_alert
from utils.logger import setup_logger

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

START_TIME = time.time()

logger = setup_logger(__name__, config.paths.log_path+"main.log")


# ---------------------------
# GLOBAL ERROR HANDLER
# ---------------------------
async def error_handler(update: Update, context: CallbackContext):
    """
    Global error handler for unhandled exceptions in the bot.
    Logs the error details, including the stack trace.
    """
    global ERROR_COUNT_24H
    ERROR_COUNT_24H += 1
    context.bot_data['error_count_24h'] = ERROR_COUNT_24H
    # Log the error details
    logger.exception(f"A general error occurred: {context.error}", exc_info=True)

    # If the error is related to a specific update, log the update details as well
    if update:
        logger.exception(f"Update: {update.to_dict()}")

    # Optionally, notify the user or the admin about the error (for debugging purposes)
    if update:
        if update.message:
            await update.message.reply_text("Sorry, an error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("Sorry, an error occurred. Please try again.")
        await send_critical_alert(
            context, title="GLOBAL ERROR",
            context_data={"user": update.effective_user.id if update.effective_user else None},
            exc=context.error
        )