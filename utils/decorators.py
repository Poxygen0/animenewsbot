from functools import wraps
from config import ADMIN_ID
from telegram.constants import ChatAction

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
        async def command_func(update, context, *args, **kwargs):
            await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=action)
            return await func(update, context,  *args, **kwargs)
        return command_func
    
    return decorator

send_typing_action = send_action(ChatAction.TYPING)
send_upload_photo_action = send_action(ChatAction.UPLOAD_PHOTO)
send_upload_video_action = send_action(ChatAction.UPLOAD_VIDEO)
send_upload_document_action = send_action(ChatAction.UPLOAD_DOCUMENT)

def restricted(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_ID:
            msg = f"Unauthorized access denied for {user_id}."
            msg_fmt = f"Unauthorized access denied to cmd:{func.__name__} for <code>{user_id}</code>."
            print(msg)
            await context.bot.send_message(chat_id=ADMIN_ID[0], text=msg_fmt)
            await update.message.reply_text("You are not authorized to use this command!")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped