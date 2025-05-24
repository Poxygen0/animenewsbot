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
# from handlers.conversation_handlers import ()
# from handlers.message_handlers import ()
from utils.logger import setup_logger

logger = setup_logger(__name__, "data/logs/main.log")

def start_bot() -> None:
    defaults = Defaults(parse_mode=ParseMode.HTML)
    app = (ApplicationBuilder()
           .token(BOT_TOKEN)
           .defaults(defaults)
           .build())
    
    
    app.add_handler(CommandHandler('start', start))
    
    app.run_polling(allowed_updates=Update.ALL_TYPES, timeout=60)


if __name__ == "__main__":
    logger.info("Bot started")
    start_bot()