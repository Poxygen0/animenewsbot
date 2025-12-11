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
from utils.logger import setup_logger

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

START_TIME = time.time()

logger = setup_logger(__name__, config.paths.log_path+"main.log")