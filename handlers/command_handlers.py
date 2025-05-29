import asyncio
from telegram import (Update,)
from telegram.constants import ParseMode, ChatAction, ChatType
from telegram.ext import ContextTypes
from models.database import SessionLocal
from models.user import User, UserSettings, SubscriptionLog, FavoriteAnime
from models.news import NewsCache
from utils.decorators import *
from utils.helpers import fetch_news_page, extract_news_articles
from const import HELP_MESSAGE, MAL_NEWS_URL

from utils.logger import setup_logger

logger = setup_logger(__name__, "./data/logs/handlers.log")


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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(HELP_MESSAGE)
    return

@send_typing_action
async def news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ''' Fetch the latest news and send it to the user '''
    try:
        with SessionLocal() as session:
            latest = NewsCache.get_latest(session)
            responses = []
            
            for article in latest:
                text = (
                    f"<b>{article.title}</b>\n"
                    f"{article.date}\n\n"
                    f"{article.summary}\n\n"
                    f"<a href='{article.link}'>Read more</a>"
                )
                responses.append(text)
        full_text = "\n\n———\n\n".join(responses)
        await update.message.reply_text(full_text)
    except Exception as e:
        logger.exception(f"❌ Failed to serve /news: {e}", exc_info=True)
        await update.message.reply_text("Couldn't load the news right now. Try again later.")
    return

