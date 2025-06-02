import asyncio
import os
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

# Admin Commands

def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True

async def update_news_articles(context: ContextTypes.DEFAULT_TYPE) -> None:
    ''' Initialize the fetching and caching of new news article at n interval '''
    logger.info("Fetching news article...")
    job = context.job
    chat_id = job.data['chat_id']
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        msg_to_edit = await context.bot.send_message(chat_id=chat_id, text="Fetching feed...")
        html_page = fetch_news_page(MAL_NEWS_URL)
        articles = extract_news_articles(html_page)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        msg_to_edit = await msg_to_edit.edit_text(text="Done")
        await asyncio.sleep(1)
        
        with SessionLocal() as session:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            msg_to_edit = await msg_to_edit.edit_text(text="Caching articles...")
            await asyncio.sleep(1)
            news_count = NewsCache.cache_articles(session, articles, max_cache=90)
        msg = f"✅ {news_count} new article(s) cached."
        logger.info(msg)
        await msg_to_edit.edit_text(msg)
    except Exception as e:
        logger.exception(f"Error whilst fetching or caching news articles: {e}")
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")
    return

@restricted
@send_typing_action
async def start_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    try:
        # Cancel existing job if any
        job_removed = remove_job_if_exists(str(chat_id), context)
        
        # Schedule the job to fetch feeds
        interval_in_seconds = 5 * 60
        job_data = {
            "chat_id": chat_id,
            }
        context.job_queue.run_repeating(update_news_articles, interval_in_seconds , chat_id=chat_id, name=str(chat_id), data=job_data)
        
        text = f"News article fetching scheduled every {interval_in_seconds/60:.2f} mins from now."
        if job_removed:
            text += "Previous schedule was canceled."
        await update.effective_message.reply_text(text)
    except Exception as e:
        logger.exception(f"An error occurred while starting schedule: {e}")
        await update.effective_message.reply_text("An error occurred while starting the schedule. Please try again.")

@restricted
@send_typing_action
async def stop_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    try:
        job_removed = remove_job_if_exists(str(chat_id), context)
        text = "Timer successfully cancelled!" if job_removed else "You have no active timer."
        await update.message.reply_text(text)
    except Exception as e:
        logger.exception(f"An error occured while stopping schedule: {e}")

@restricted
@send_typing_action
async def log_preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_path = "./data/logs/handlers.log"
    if not os.path.exists(log_path):
        await update.message.reply_text("No log file found.")
        return

    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()[-40:]  # Tail last 40 lines

    log_text = "".join(lines)
    await update.message.reply_text(f"📄 Recent logs:\n\n<pre>{log_text}</pre>")
    return

