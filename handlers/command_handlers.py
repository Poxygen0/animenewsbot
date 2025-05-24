import asyncio
from telegram import (Update,)
from telegram.constants import ParseMode, ChatAction, ChatType
from telegram.ext import ContextTypes
from utils.decorators import *


@send_typing_action
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ''' Send a message when the command /start is issued.'''
    # Gather user and chat details from the update
    user = update.effective_user
    chat = update.effective_chat
    
    user_data = {
        "id": user.id,
        "chat_id": chat.id,
        "first_name": chat.first_name,
        "last_name": chat.last_name,
        "username": user.username,
    }
    welcome_message = f"👋 Hello {user_data.get('first_name', 'there')}, Welcome to the Anime News Bot! Type /help to see what I can do."
    
    await update.message.reply_text(welcome_message)
    return