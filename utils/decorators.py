from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from config import config
from .helpers import is_owner
from utils.logger import setup_logger

logger = setup_logger(__name__, "./data/logs/utils.log")

def send_action(action):
    """Sends `action` while processing func command.
    You can decorate handler callbacks directly with @send_action(ChatAction.<Action>) or create aliases and decorate with them (more readable) .

    send_typing_action = send_action(ChatAction.TYPING)
    send_upload_video_action = send_action(ChatAction.UPLOAD_VIDEO)
    send_upload_photo_action = send_action(ChatAction.UPLOAD_PHOTO)

    With the above aliases, the following decorators are equivalent

    @send_typing_action
    async def my_handler(update, context):
        pass  # user will see 'typing' while your bot is handling the request.
        
    @send_action(ChatAction.TYPING)
    async def my_handler(update, context):
        pass  # user will see 'typing' while your bot is handling the request.
    """

    def decorator(func):
        @wraps(func)
        async def command_func(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=action)
            return await func(update, context,  *args, **kwargs)
        return command_func
    
    return decorator

send_typing_action = send_action(ChatAction.TYPING)
send_upload_photo_action = send_action(ChatAction.UPLOAD_PHOTO)

def restricted(func):
    """ Decorator to restrict a command handler to administrators only. """
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not is_owner(user_id):
            msg = f"Unauthorized access denied for {user_id}."
            msg_fmt = f"Unauthorized access denied to cmd:{func.__name__} for <code>{user_id}</code>."
            logger.info(msg)
            await context.bot.send_message(chat_id=config.bot.owner_id, text=msg_fmt)
            await update.message.reply_text("<b>🚫 Unauthorized access</b>")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped