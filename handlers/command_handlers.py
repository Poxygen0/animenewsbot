import asyncio
import os
import time
from telegram import (
    Update,InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.constants import ParseMode, ChatAction, ChatType
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from models.database import SessionLocal
from models.user import (
    User, UserSettings, SubscriptionLog, Channel,
    )
from models.news import NewsCache
from utils.decorators import *
from utils.helpers import (
    fetch_news_page, extract_news_articles, format_uptime,
    resize_and_process_image, send_critical_alert, escape_html,
    is_owner)
from const import HELP_MENU, ADMIN_MENU, ERROR_MSG


from utils.logger import setup_logger

logger = setup_logger(__name__, "./data/logs/handlers.log")

async def delete_old_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mid = context.user_data.get("last_menu_id")
    if mid:
        try:
            await update.effective_chat.delete_message(mid)
            context.user_data.pop('last_menu_id', None)
        except:
            pass

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
        "language_code": user.language_code,
    }
    welcome_message = f"👋 Hello {escape_html(user_data.get('first_name', 'there'))}, use /help for a list of commands."
    await update.message.reply_text(welcome_message)
    
    with SessionLocal() as session:
        try:
            is_existing_user = User.user_exists(session, user_data["id"], user_data["chat_id"])
            
            if not is_existing_user:
                new_user = User(**user_data)
                u_settings = UserSettings(user_id=user_data["id"])
                session.add(new_user)
                session.add(u_settings)
                session.commit()
                return
        except ValueError as e:
            session.rollback()
            logger.exception(f"Registration error: {e}")
            return
        except Exception as e:
            session.rollback()
            logger.exception(f"Error during user registration: {str(e)}")
            await send_critical_alert(context, "Error while processing a user registration.", user_data, exc=e)
            # await context.bot.send_message(chat_id=config.bot.owner_id, text="An error occurred while processing a user registration.")
            return
    
    return

@send_typing_action
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays command information."""
    help_text = HELP_MENU
    if is_owner(update.effective_user.id):
        help_text += ADMIN_MENU
        
    await update.message.reply_text(help_text)
    return






@send_typing_action
async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

####################
#   User Settings  #
####################

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ''' Subscribe to receive news on an interval basis '''
    user = update.effective_user
    with SessionLocal() as session:
        try:
            user_settings = UserSettings.get_user_settings(session, user.id)
            
            # Check if notifications are already muted
            if user_settings is not None and user_settings.is_subscribed:
                await update.effective_message.reply_text("You are already subscribed.")
                return
            user_settings.update_user_settings(session, user_id=user.id, subscribed=True)
            await update.effective_message.reply_text("You will now receive scheduled updates.\nTo unsubscribe use: /unsubscribe.")
        except Exception as e:
            session.rollback()
            logger.exception(f"Error during subscription: {str(e)}")
            await update.effective_message.reply_text("An error occurred on our side while subscribing.")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ''' Unsubscribe to stop news update schedule '''
    user = update.effective_user
    with SessionLocal() as session:
        try:
            user_settings = UserSettings.get_user_settings(session, user.id)
            
            # Check if notifications are already muted
            if user_settings is not None and not user_settings.is_subscribed:
                await update.effective_message.reply_text("You are already not subscribed.")
                return
            user_settings.update_user_settings(session, user_id=user.id, subscribed=False)
            await update.effective_message.reply_text("You will stop receiving scheduled updates from now.")
        except Exception as e:
            session.rollback()
            logger.exception(f"Error during subscription: {str(e)}")
            await update.effective_message.reply_text("An error occurred on our side while subscribing.")

async def channel_updates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ''' Subscribe to receive news on an interval basis in added channels '''
    user = update.effective_user
    with SessionLocal() as session:
        try:
            user_settings = UserSettings.get_user_settings(session, user.id)
            
            # Check if notifications are already muted
            if user_settings is not None and user_settings.opted_for_channel_updates:
                await update.effective_message.reply_text("You are already subscribed for channel updates.")
                return
            user_settings.update_user_settings(session, user_id=user.id, opted_for_channel_updates=True)
            await update.effective_message.reply_text("You will now receive scheduled updates in all your added channels.\nTo unsubscribe use: /unsubscribe_channel.")
        except Exception as e:
            logger.exception(f"Error during channel subscription: {str(e)}")
            await update.effective_message.reply_text("An error occurred on our side while adding your channel.")

async def unchannel_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ''' Unsubscribe to stop news update schedule in channels '''
    user = update.effective_user
    with SessionLocal() as session:
        try:
            user_settings = UserSettings.get_user_settings(session, user.id)
            
            # Check if subscrition is are already false
            if user_settings is not None and not user_settings.opted_for_channel_updates:
                await update.effective_message.reply_text("You are already not subscribed for channel updates.")
                return
            user_settings.update_user_settings(session, user_id=user.id, opted_for_channel_updates=False)
            await update.effective_message.reply_text("You will stop receiving scheduled updates in added channels from now.")
        except Exception as e:
            logger.exception(f"Error during channel subscription: {str(e)}")
            await update.effective_message.reply_text("An error occurred on our side while removing your channel.")


async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    with SessionLocal() as session:
        try:
            # Check for arguments
            if len(context.args) == 0:
                # If no argument, get current setting
                user_settings = UserSettings.create_or_get_user_settings(session, user.id)
                new_setting = not user_settings.notifications_disabled # Toggle the current state
                if UserSettings.update_notifications_disabled(session ,user_id=user.id, notification_in=new_setting):
                    status_message = "Notifications are now turned OFF." if new_setting else "Notifications are now turned ON."
                    await update.effective_message.reply_text(status_message)
                else:
                    await update.effective_message.reply_text("Failed to update your notification settings.")
                return
            
            # Ensure user has sent exactly one expected valid argument ('on' or 'off')
            if len(context.args) != 1:
                await update.effective_message.reply_text(
                    "Usage: /togglenotifications <on | off> or /togglenotifications",
                    parse_mode=ParseMode.MARKDOWN)
                return

            new_notification = str(context.args[0]).lower()
            if new_notification not in ("on", "off"):
                await update.effective_message.reply_text("Please specify either 'on' or 'off' for notifications.")
                return

            # Convert input to boolean
            notification_setting = new_notification == "off"
            # Store the new interval (can be stored in the database or in-memory)
            if UserSettings.update_notifications_disabled(session, user_id=user.id, notification_in=notification_setting):
                # Inform the user about the update
                await update.effective_message.reply_text(f"Notifications are now {'muted' if notification_setting else 'enabled'}.")
            else:
                await update.effective_message.reply_text("Failed to update your notification settings.")
            return

        except Exception as e:
            logger.exception(f"Error during toggle_notifications: {str(e)}")
            await update.message.reply_text("An error occurred while updating your notification settings.")
            return

####################
#  Admin Commands  #
####################

@restricted
@send_typing_action
async def admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(ADMIN_MENU)

# Fallback handler for all other messages
async def ignore_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Ignores everything that is not a command we recognize
    await update.message.reply_text("Sorry, I do not understand. Use /help for a list of available commands.")
    return

@restricted
@send_typing_action
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    start_time = context.bot_data.get("start_time")

    if not start_time:
        await update.message.reply_text("❌ Bot start time not found.")
        return

    # Calculate uptime
    # uptime = time.time() - start_time
    # hours, remainder = divmod(int(uptime), 3600)
    # minutes, seconds = divmod(remainder, 60)
    uptime_seconds = time.time() - start_time
    uptime_text = format_uptime(uptime_seconds)
    with SessionLocal() as session:
        try:
            total_users: int = User.get_total_users(session=session)
            status = (
                f"<b>Status</b>\n\n"
                f"<b>🤖 Bot Status</b>: Online\n"
                # f"<b>⏱️ Uptime</b>: {hours}h {minutes}m {seconds}s\n"
                f"<b>⏱️ Uptime</b>: {uptime_text}\n"
                f"<b>👥 Total Users</b>: {total_users}")
            await update.message.reply_text(status)
        except Exception as e:
            await update.message.reply_text(f"There was an error fetching status: {e}")

def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True

# --------------------------------------------
# Send News to Subscribers

async def send_news_to_subscribers(news, chat_ids, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send new news to subscribers or channels."""
    if not news:
        logger.info("No new news articles to send.")
        return

    # Helper function to send the news to a single chat (user or channel)
    async def send_to_chat(chat_id, article, is_channel=False):
        message_text = f"<b>{article.get('title')}</b>\n\n<i>{article.get('summary')}</i>"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 Read More", url=article.get('link'))]
        ])

        if article.get('image_url'):
            try:
                # Send photo for both users and channels
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=article.get('image_url'),
                    caption=message_text,
                    reply_markup=keyboard)
            except Exception as e:
                logger.exception(f"Failed to send photo to chat {chat_id}: {str(e)}")
        else:
            try:
                # Send message for both users and channels
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    reply_markup=keyboard)
            except Exception as e:
                logger.exception(f"Failed to send message to chat {chat_id}: {str(e)}")

    # Send news to channels (always with buttons)
    for chat_id in chat_ids:
        if chat_id < 0:  # Channel ID check
            for article in news:
                await send_to_chat(chat_id, article, is_channel=True)

    # For users: handle based on the number of news articles
    if len(news) < 5:
        # Send individual articles to user_ids
        for chat_id in chat_ids:
            if chat_id > 0:  # User ID check
                for article in news:
                    await send_to_chat(chat_id, article)
    else:
        # Send clickable headlines to users if there are 6 or more articles
        headlines_text = "<b>Latest News:</b>\n\n"
        for article in news:
            headlines_text += f"- <a href='{article.get('link')}'>{article.get('title')}</a>\n"

        for chat_id in chat_ids:
            if chat_id > 0:  # User ID check
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=headlines_text)
                except Exception as e:
                    logger.exception(f"Failed to send message to user {chat_id}: {str(e)}")


async def update_news_articles(context: ContextTypes.DEFAULT_TYPE) -> None:
    ''' Initialize the fetching and caching of new news article at n interval '''
    logger.info("Fetching news article...")
    job = context.job
    chat_id = job.data['chat_id']
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        msg_to_edit = await context.bot.send_message(chat_id=chat_id, text="Fetching feed...")
        html_page = fetch_news_page(config.settings.mal_news_url)
        articles = extract_news_articles(html_page)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        msg_to_edit = await msg_to_edit.edit_text(text="Done")
        await asyncio.sleep(1)
        
        with SessionLocal() as session:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            msg_to_edit = await msg_to_edit.edit_text(text="Caching articles...")
            await asyncio.sleep(1)
            news_count, new_news = NewsCache.cache_articles(session, articles)
        msg = f"✅ {news_count} new article(s) cached."
        logger.info(msg)
        await msg_to_edit.edit_text(msg)
        if new_news:
            try:
                with SessionLocal() as session:
                    user_chat_ids = UserSettings.get_all_subscribed_users(session)
                    opted_for_channel = UserSettings.get_all_opted_users(session)
                    channel_ids = [channel.id for user_id in opted_for_channel for channel in Channel.get_all_user_channels(session, user_id)]
                    chat_ids = user_chat_ids + channel_ids
            except Exception as e:
                logger.exception(f"Error whilst fetching subscribed users: {e}")
                msg_title = "Error whilst fetching subscribed users"
                await send_critical_alert(context, msg_title, context.bot_data, exc=e)
                # await context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")
            # Send the new news to subscribers
            await send_news_to_subscribers(new_news, chat_ids, context)
    except Exception as e:
        logger.exception(f"Error whilst fetching or caching news articles: {e}")
        msg_title = "Error whilst fetching or caching news articles"
        await send_critical_alert(context, msg_title, context.bot_data, exc=e)
        # await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        # await context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")
    return

@restricted
@send_typing_action
async def start_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    try:
        # Cancel existing job if any
        job_removed = remove_job_if_exists(str(chat_id), context)
        
        # Schedule the job to fetch news
        job_data = {
            "chat_id": chat_id,
            }
        context.job_queue.run_repeating(update_news_articles, config.settings.interval_in_secs , chat_id=chat_id, name=str(chat_id), data=job_data)
        
        text = f"News article fetching scheduled every {config.settings.interval_in_secs/60:.2f} mins from now."
        if job_removed:
            text += "Previous schedule was canceled."
        await update.effective_message.reply_text(text)
    except Exception as e:
        logger.exception(f"An error occurred while starting schedule: {e}")
        msg_title = "An error occurred while starting schedule"
        await send_critical_alert(context, msg_title, context.bot_data, exc=e)
        # await update.effective_message.reply_text("An error occurred while starting the schedule. Please try again.")

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
        msg_title = "An error occured while stopping schedule"
        await send_critical_alert(context, msg_title, context.bot_data, exc=e)


@restricted
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ''' Command: /broadcast - Send a message to all users (Admin Only) '''
    uchat_id = update.effective_chat.id

    # Ensure there's a message to broadcast
    if len(context.args) == 0:
        await context.bot.send_chat_action(chat_id=uchat_id, action=ChatAction.TYPING)
        await update.message.reply_text("Usage: /broadcast <message>", parse_mode=ParseMode.MARKDOWN)
        return

    message_to_broadcast = " ".join(context.args)
    msg_failed = []
    msg_sent = []

    # fetch all users
    with SessionLocal() as session:
        try:
            # Fetch all users
            user_chat_ids = User.get_all_chatIds(session)

            # Broadcast the message to each user
            for chat_id in user_chat_ids:
                try:
                    await context.bot.send_chat_action(chat_id=chat_id[0], action=ChatAction.TYPING)
                    await context.bot.send_message(chat_id=chat_id[0], text=message_to_broadcast)
                    logger.info(f"Message sent to {chat_id[0]}")
                    msg_sent.append(chat_id[0])
                except BadRequest as e:
                    await update.message.reply_text(f"BadRequest: {e}")
                    logger.exception(f"Error: {e}")
                    msg_failed.append(chat_id[0])
                    return
                except Exception as e:
                    logger.exception(f"Failed to send message to {chat_id[0]}: {str(e)}")
                    msg_title = f"Failed to send message to {chat_id[0]}"
                    msg_failed.append(chat_id[0])
                    await send_critical_alert(context, msg_title, context.bot_data, exc=e)

            isSuccessful = "successfully" if not msg_failed else f"with {len(msg_failed)} errors"
            await context.bot.send_chat_action(chat_id=uchat_id, action=ChatAction.TYPING)
            await update.message.reply_text(f"📢 Broadcast message sent {isSuccessful}.\n<b>✅ Sent to:</b> {len(msg_sent)} chats.\n<b>❌ Failed:</b> {len(msg_failed)}")
            logger.info(f"Broadcast message sent {isSuccessful}.\nSent to: {len(msg_sent)}chats.\nFailed: {len(msg_failed)}")
            return

        except BadRequest as e:
                    await update.message.reply_text(f"BadRequest: {e}")
                    logger.exception(f"Error: {e}")
                    return
        except Exception as e:
            logger.exception(f"Error during broadcast: {str(e)}")
            msg_title = "Error during broadcast"
            await send_critical_alert(context, msg_title, context.bot_data, exc=e)
            # await update.message.reply_text("An error occurred while broadcasting the message.")
            return

# End of Admin commands