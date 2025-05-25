from telegram import (Update, ReplyKeyboardRemove, ReplyKeyboardMarkup)
from telegram.constants import ParseMode, ChatAction
from telegram.ext import ContextTypes, ConversationHandler
from utils.decorators import *
from utils.logger import setup_logger
from config import ADMIN_ID

logger = setup_logger(__name__, "./data/logs/handlers.log")

FEEDBACK = range(1)


async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    ''' For user feedback '''
    # Ask for feedback
    await update.message.reply_text("Please provide your feedback:")
    return FEEDBACK

async def received_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    ''' Handle user feedback '''
    user = update.effective_user
    user_feedback = update.message.text # This is the feedback message from the user
    
    try:
        # Send the feedback directly to the admin
        await context.bot.send_message(chat_id=ADMIN_ID[0], text=f"Feedback from {user.first_name} (ID: {user.id}):\n\n{user_feedback}")
        # Let the user know their feedback has been sent
        await update.message.reply_text("Thank you for your feedback! It has been forwarded to the admin.")
    except Exception as e:
        logger.exception(f"Error sending user feedback: {e}")
        logger.info(f"Feedback from {user.first_name} (ID: {user.id}):\n\n{user_feedback}")
        await update.message.reply_text("Oops🙊, seems there's an error.\n(Either unsupported characters or an error on our side)")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    # Edit message to remove the buttons
    # query = update.callback_query
    # if query:
    #     await query.edit_message_text(reply_markup=None)

    user = update.message.from_user
    first_name = user.first_name
    user_id = update.effective_user.id
    logger.info(f"User: ({user_id},{first_name}) canceled the conversation.")
    print(f"Operation cancelled by ({user_id},{first_name})")
    await update.message.reply_text(
        "Operation cancelled.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END