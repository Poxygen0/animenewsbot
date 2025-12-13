import time
import os
from datetime import datetime

# Telegram
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    AIORateLimiter,
    Application,
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


from handlers.command_handlers import (
    admin_commands,
    broadcast,
    channel_updates,
    help_command,
    ignore_all,
    latest,
    start,
    start_schedule,
    status,
    stop_schedule,
    subscribe,
    toggle_notifications,
    unchannel_update,
    unsubscribe,
)
from handlers.conversation_handlers import (
    add_channel,
    handle_cancel,
    handle_add_channel,
    mychannels,
    handle_mychannels,
    feedback,
    received_feedback,
    latest_news,
    handle_selected_news,
    timeout,
    cancel,
    FEEDBACK,
    FORWARD_MESSAGE,
    SELECTING_CHANNEL,
    SELECTING_NEWS,
)
# from handlers.message_handlers import ()
from config import config
from models.database import Base, db
from utils.helpers import send_critical_alert
from utils.logger import setup_logger

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

START_TIME = time.time()
ERROR_COUNT_24H = 0

logger = setup_logger(__name__, config.paths.log_path+"/main.log")

def init_db():
    """Creates tables if they don't exist."""
    Base.metadata.create_all(db)

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

async def post_init(app: Application) -> None:
    """Runs after the bot is started and persistence data is loaded."""
    
    # Set/Update the Bot Start Time (Crucial for uptime calculation)
    # This must run AFTER persistence is loaded to ensure it reflects the *current* uptime.
    app.bot_data['start_time'] = START_TIME
    logger.info(f"Bot start time set to {datetime.fromtimestamp(START_TIME)}.")
    app.bot_data['error_count_24h'] = ERROR_COUNT_24H
    logger.info(f"Bot error count set to {ERROR_COUNT_24H}.")
    
    logger.info("post_init is complete.")

def start_bot() -> None:
    """The main entry point for the bot."""
    # Initializing db
    init_db()
    
    defaults = Defaults(parse_mode=ParseMode.HTML)
    # Configure the rate limiter
    rate_limiter = AIORateLimiter(
        overall_max_rate=config.settings.overall_max_rate,      # Max 30 requests per second across all chats
        overall_time_period=config.settings.overall_time_period,
        group_max_rate=config.settings.group_max_rate,        # Max 20 requests per minute in a single group
        group_time_period=config.settings.group_time_period
    )
    # persistence... Uncomment the code below for persistence
    # persistence = PicklePersistence(filepath="data/districtbot_persistence.pkl")
    
    app = (ApplicationBuilder()
           .token(config.bot.token)
           .defaults(defaults)
           .rate_limiter(rate_limiter)
        #    .persistence(persistence) # Uncomment for persistend
           .post_init(post_init)
           .build())
    

    ##################################################
    #           Conversation Handlers here           #
    ##################################################
    
    conv_handler_channel = ConversationHandler(
        entry_points=[
            CommandHandler('mychannels', mychannels, filters=filters.ChatType.PRIVATE),
            CommandHandler('add_channel', add_channel, filters=filters.ChatType.PRIVATE),
            ],
        states={
            SELECTING_CHANNEL: [CallbackQueryHandler(handle_mychannels, pattern="^cha*"),
                                CallbackQueryHandler(handle_cancel, pattern="^cancel$"),
                                CallbackQueryHandler(add_channel, pattern="^add_channel_button$"),],
            FORWARD_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, handle_add_channel),
                              CallbackQueryHandler(handle_cancel, pattern="^cancel$")],
            },
        fallbacks=[CommandHandler('cancel', cancel, filters=filters.ChatType.PRIVATE)],
        conversation_timeout=400,
    )
    
    conv_handler_feedback = ConversationHandler(
        entry_points=[CommandHandler('feedback', feedback, filters=filters.ChatType.PRIVATE)],
        states={
            FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_feedback)]
        },
        fallbacks=[CommandHandler("cancel", cancel, filters=filters.ChatType.PRIVATE)],
    )
    
    conv_handler_news = ConversationHandler(
        entry_points=[CommandHandler('latest', latest_news, filters=filters.ChatType.PRIVATE)],
        states={
            SELECTING_NEWS: [CallbackQueryHandler(handle_selected_news, pattern="^news*"),
                             CallbackQueryHandler(handle_cancel, pattern="^cancel$")]
        },
        fallbacks=[CommandHandler('cancel', cancel, filters=filters.ChatType.PRIVATE)],
        conversation_timeout=400,
    )
    
    ##############################################
    #       Commands and Callback handlers       #
    ##############################################
    app.add_handler(CommandHandler('start', start, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('help', help_command, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('togglenotifications', toggle_notifications, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('subscribe', subscribe, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('unsubscribe', unsubscribe, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('subscribe_channel', channel_updates, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('unsubscribe_channel', unchannel_update, filters=filters.ChatType.PRIVATE))
    
    #############################
    #       Admin commands      #
    #############################
    app.add_handler(CommandHandler('skfj_start_schedule', start_schedule, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('skfj_stop_schedule', stop_schedule, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('skfj_broadcast', broadcast, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('skfj_admin_commands', admin_commands, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('skfj_status', status, filters=filters.ChatType.PRIVATE))
    
    #####################################
    #       conversation handlers       #
    #####################################
    app.add_handler(conv_handler_channel)
    app.add_handler(conv_handler_feedback)
    app.add_handler(conv_handler_news)
    
    
    # Ignoring all other messages
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, ignore_all))
    
    # Register the global error handler
    app.add_error_handler(error_handler)
    
    logger.info("Starting bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, timeout=config.bot.timeout)

if __name__ == "__main__":
    logger.info("Script started")
    start_bot()