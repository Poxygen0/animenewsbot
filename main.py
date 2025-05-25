import logging
from config import BOT_TOKEN
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Defaults,
    filters,
    MessageHandler,
)
from handlers.command_handlers import (
    start,
)
from handlers.conversation_handlers import (
    feedback,
    received_feedback,
    cancel,
    FEEDBACK
)
# from handlers.message_handlers import ()
from utils.logger import setup_logger

logger = setup_logger(__name__, "data/logs/main.log")

def start_bot() -> None:
    defaults = Defaults(parse_mode=ParseMode.HTML)
    app = (ApplicationBuilder()
           .token(BOT_TOKEN)
           .defaults(defaults)
           .build())
    
    # Add Conversation Handlers here
    conv_handler_feedback = ConversationHandler(
        entry_points=[CommandHandler('feedback', feedback)],
        states={
            FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_feedback)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # commands
    app.add_handler(CommandHandler('start', start))
    # conversation handlers
    app.add_handler(conv_handler_feedback)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES, timeout=60)


if __name__ == "__main__":
    logger.info("Bot started")
    start_bot()