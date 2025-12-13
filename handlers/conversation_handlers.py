import asyncio
import re
from textwrap import dedent

from telegram import (
    Update, ReplyKeyboardRemove, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InputMedia,)
from telegram.constants import ParseMode, ChatAction, ChatType, MessageType
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import effective_message_type
from telegram.error import TelegramError, BadRequest

from sqlalchemy.orm import Session

from models.database import SessionLocal
from models.user import User, UserSettings, Channel
from models.news import NewsCache
from utils.decorators import *
from utils.helpers import (
    build_menu, get_data_paginated, get_channels, get_news,
    get_user_channels, send_critical_alert, escape_html,
    is_owner)
from config import config
from const import HELP_MENU, ADMIN_CHECK_FAILURE, ERROR_MSG


from utils.logger import setup_logger

logger = setup_logger(__name__, "./data/logs/handlers.log")


# Conversation handling states
FORWARD_MESSAGE, FEEDBACK, SELECTING_CHANNEL = range(3)
SELECTING_NEWS = range(1)


async def delete_old_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mid = context.user_data.get("last_menu_id")
    if mid:
        try:
            await update.effective_chat.delete_message(mid)
            context.user_data.pop('last_menu_id', None)
        except:
            pass


@send_typing_action
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Adding a new channel to the database """
    txt = f"""
    *Adding a channel*
    
To add a channel you should follow these two steps:
    
1️⃣ Add {config.bot.username} to admins of your channel and grant it posting permission.
2️⃣ Then forward to me any message from your channel (or send me its @username / t.me link / ID).
    """
    keyboard = [
        [InlineKeyboardButton("Cancel", callback_data='cancel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(txt, disable_web_page_preview=True,reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return FORWARD_MESSAGE
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await update.callback_query.edit_message_text(txt, disable_web_page_preview=True,reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return FORWARD_MESSAGE

# Helper function to handle the core channel processing logic
async def _process_channel(session: Session, update: Update, context: ContextTypes.DEFAULT_TYPE, channel, user_id: int):
    """
    Handles the core logic for processing and adding a channel.
    """
    try:
        # Check if bot is an admin in the channel and has required permissions
        bot_member = await context.bot.get_chat_member(chat_id=channel.id, user_id=context.bot.id)
        if not (bot_member.status == 'administrator' and bot_member.can_post_messages):
            await update.message.reply_text(ADMIN_CHECK_FAILURE)
            # (
            #     f"I am not an admin with the required 'post messages' and 'delete messages' permissions "
            #     f"in {escape_html(channel.title)}. Please grant me these permissions and try again."
            # )
            return ConversationHandler.END
        
        # --- USER PERMISSIONS CHECK ---
        user_member = await context.bot.get_chat_member(chat_id=channel.id, user_id=user_id)
        if user_member.status not in ['administrator', 'creator']:
            await update.message.reply_text(
                "🚫You are not an admin in the channel. I can't process this."
            )
            return ConversationHandler.END
        
        # Check if exists
        exists: bool = Channel.channel_exists(session, channel.id)
        if exists:
            prod_text = dedent(f"""
            ℹ️ The channel <b>{escape_html(channel.title)}</b> is already registered.
            
            Forward another channel's message or contact the channel owner for help.
            """)
            await update.effective_message.reply_text(prod_text, disable_web_page_preview=True)
            return FORWARD_MESSAGE

        # Save new channel
        new_channel = Channel(
            id=channel.id,
            name=channel.title,
            username= f"https://t.me/{channel.username}" if channel.username else "",
            added_by=user_id,
        )
        session.add(new_channel)
        session.commit()
        context.user_data.pop("channels", None)

        # Notify user and owner
        await update.effective_message.reply_text(
            f"✅ Channel <b>{channel.title}</b> added successfully!"
        )
        return ConversationHandler.END

    except BadRequest as e:
        # Handle the specific error: "Member list is inaccessible"
        if "Member list is inaccessible" in str(e):
            await update.message.reply_text(
                f"Error: I'm not an admin in {escape_html(channel.title)}."
                "Please ensure the bot is an admin in the channel and that all required settings "
                "are enabled, then try again."
                "This can happen if the channel is private or configured with anonymous admins. "
            )
        else:
            # Handle other types of BadRequest errors
            await update.message.reply_text(f"Telegram API Error: {e}")
            await send_critical_alert(
            context, title="Telegram API Error",
            context_data={"user": update.effective_user.id},
            exc=e
        )
            logger.exception(f"Telegram API Error processing channel: {e}")
        return ConversationHandler.END
    except TypeError as e:
        # Occurs with private channels; still consider it a success for now.
        text = f"Success! The channel <b>{escape_html(channel.title)}</b> has been added."
        await update.message.reply_text(text, disable_web_page_preview=True)
        context.user_data.pop("channels", None)
        logger.info(f"Private channel added: {channel.title}")
        logger.exception(f"{e}")
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text("An unexpected error occurred. Please try again later.")
        await send_critical_alert(
            context, title="Unexpected Error in processing channel",
            context_data={"user": update.effective_user.id, "channel":channel.id, "channel name":escape_html(channel.title)},
            exc=e
        )
        logger.exception(f"Error processing channel: {e}")
        return ConversationHandler.END

@send_typing_action
async def handle_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    user_id = update.effective_user.id
    msg = update.effective_message

    with SessionLocal() as session:
        try:
            # Forwarded message from channel
            if msg.forward_origin and msg.forward_origin.type == ChatType.CHANNEL:
                channel = msg.forward_origin.chat
                return await _process_channel(
                    session, update,context,
                    channel, user_id)

            # Username / link / ID input
            if msg.text:
                text = msg.text.strip()
                identifier = None
                # t.me link or @username
                if text.startswith('@'):
                    identifier = text
                elif text.startswith('https://t.me/'):
                    identifier = "@" + text.split('/')[-1]
                elif text.lstrip('-').isdigit():
                    identifier = int(text)
                    
                if identifier is None:
                        await msg.reply_text("Please provide a valid @username, `t.me` link, or Channel ID.")
                        return FORWARD_MESSAGE
                
                try:    
                    chat = await context.bot.get_chat(identifier)
                    if chat.type != ChatType.CHANNEL:
                        await msg.reply_text(f"{identifier} is not a channel.")
                        return FORWARD_MESSAGE
                    return await _process_channel(session, update, context, chat, user_id)
                except TelegramError as e:
                        await msg.reply_text(
                            "I couldn't access that channel. Ensure it is public or forward a message from it and make me an admin."
                        )
                        return FORWARD_MESSAGE
                        

            await msg.reply_text("Forward a message from the channel or send it's @username, t.me link, or ID.")
            return FORWARD_MESSAGE
        
        except Exception as e:
            logger.exception(f"Error in handle_add_channel logic: {e}")
            await send_critical_alert(context, 'Error in handle_add_channel logic',
                                context.user_data, exc=e)
            await msg.reply_text("An unexpected error occurred during channel addition.\nPlease try again")
            return ConversationHandler.END
        


@send_typing_action
async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Handles the cancel action, either by deleting a photo message or editing text."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("cancel"):
        # Check the type of message (photo or text)
        msg_type = effective_message_type(update)

        try:
            if msg_type == MessageType.PHOTO:
                # If the message is a photo, delete it and send a cancellation message
                await query.delete_message()  # Deletes the current photo message
                await context.bot.send_message(update.effective_chat.id, "Operation cancelled.")
            else:
                # If it's not a photo, just edit the message to indicate cancellation
                await query.edit_message_text("Operation cancelled.")
            
            return ConversationHandler.END
        except Exception as e:
            logger.exception(f"Error handling cancel: {e}")
            # In case of error (e.g., message already deleted or other issues), send a fallback message
            await query.edit_message_text("Operation cancelled (with an error).")
            await send_critical_alert(
                context, title="Unexpected Error in handling cancel",
                context_data={"user": update.effective_user.id},
                exc=e
            )
            return ConversationHandler.END
    return ConversationHandler.END


@send_typing_action
async def show_channel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1) -> int | None:
    """
    Displays channels in a grid with navigation options.

    Args:
        update (Update): Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): Context object.

    Returns:
        None
    """
    txt: str = "<b>Channel management</b> \n\nChoose a channel from the list below:"
    user_id: int = update.effective_user.id
    page: int = int(context.args[0]) if context.args else 1 # Default to page 1
    channels: list = context.user_data.get("channels")
    
    if not channels:
        # Mock: Fetch channels once and store in user_data
        channels: list = get_user_channels(user_id)
        if not channels:
            text = "You haven't added any channel yet. Use /add_channel to add a channel."
            if update.message:
                await update.message.reply_text(text)
                return ConversationHandler.END
            elif update.callback_query: # Callback query context
                await update.callback_query.edit_message_text(text)
                return ConversationHandler.END
        # print(channels)
        context.user_data["channels"] = channels # Cache it in user_data
    paginated_channels, has_next = get_data_paginated(channels, page)
    
    # Create InlineKeyboardButton objects for channels
    buttons: list = [
        InlineKeyboardButton(channel.name, callback_data=f"cha_select_channel_{channel.id}")
        for channel in paginated_channels
    ]
    
    # Add navigation buttons
    header_buttons: list = [
        InlineKeyboardButton("➕ Add Channel", callback_data="add_channel_button")
    ]
    footer_buttons: list = []
    special_footer: list = []
    if has_next:
        footer_buttons.append(InlineKeyboardButton("»", callback_data=f"cha_navigate_page_{page + 1}"))
    if page > 1:
        footer_buttons.append(InlineKeyboardButton("«", callback_data=f"cha_navigate_page_{page - 1}"))
    special_footer.append(InlineKeyboardButton("Cancel", callback_data='cancel'))
    # Build keyboard using build_menu
    keyboard = build_menu(buttons, n_cols=2, header_buttons=header_buttons, footer_buttons=footer_buttons, special_footer=special_footer)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Handle both message and callback query contexts
    if update.message: # Command context
        await update.message.reply_text(txt, reply_markup=reply_markup)
        # return SELECTING_CHANNEL
    elif update.callback_query: # Callback query context
        await update.callback_query.edit_message_text(txt, reply_markup=reply_markup)
    return SELECTING_CHANNEL

async def mychannels(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """The entry point command handler."""
    # This handler will simply call the reusable menu function
    return await show_channel_menu(update, context)

# @send_typing_action
async def handle_mychannels(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """
    Handles callback queries for navigation and channel selection.

    Args:
        update (Update): Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): Context object.

    Returns:
        None
    """
    query = update.callback_query
    await query.answer()

    if query.data.startswith("cha_navigate_page_"):
        # Extract page number and re-render
        page = int(query.data.split("_")[-1])
        context.args = [str(page)]  # Update context.args for pagination
        # logger.info("channel navigation")
        await show_channel_menu(update, context, page)
        return SELECTING_CHANNEL
    elif query.data.startswith("cha_select_channel_"):
        # Handle channel selection
        channel_id = int(query.data.split("_")[-1])
        # Get channel info from cached list
        channels = context.user_data.get("channels", [])
        selected = next((c for c in channels if c.id == channel_id), None)
        
        if not selected:
            await query.edit_message_text("Channel not found or no longer exists.")
            return ConversationHandler.END
        
        context.user_data["selected_channel_id"] = channel_id
        text = f"✅ <b>Channel:</b> <code>{selected.name}</code> is selected."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Delete Channel", callback_data=f"cha_delete_{channel_id}")],
            [InlineKeyboardButton("⬅️ Back", callback_data="cha_navigate_page_1")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return SELECTING_CHANNEL
    elif query.data.startswith("cha_delete_"):
        channel_id = int(query.data.split("_")[-1])

        # Simulate deletion (e.g., from DB)
        # delete_channel(channel_id)
        with SessionLocal() as session:
            success = Channel.delete_channel(session, channel_id)
        if success:
            # Update user_data cache
            channels = context.user_data.get("channels", [])
            context.user_data["channels"] = [c for c in channels if c.id != channel_id]
            text = "❌ Channel deleted."
        else:
            text = "⚠️ Channel not found or already deleted."
        # Show back button either way
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="cha_navigate_page_1")]
        ])

        await query.edit_message_text(text=text, reply_markup=keyboard)
        return SELECTING_CHANNEL
    elif query.data == 'cha_1':
        # long wait for something
        await asyncio.sleep(5)
        await query.edit_message_text(text=f"You did it")
        return ConversationHandler.END

@send_typing_action
async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    ''' For user feedback '''
    # Ask for feedback
    await update.message.reply_text("Please provide your feedback:")
    return FEEDBACK

@send_typing_action
async def received_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    ''' Handle user feedback '''
    user = update.effective_user
    user_feedback = escape_html(update.message.text) # This is the feedback message from the user
    
    try:
        # Send the feedback directly to the admin
        await context.bot.send_message(chat_id=config.bot.owner_id, text=f"Feedback from {user.first_name} (ID: {user.id}):\n\n{user_feedback}")
        # Let the user know their feedback has been sent
        await update.message.reply_text("Thank you for your feedback! It has been forwarded to the admin.")
    except Exception as e:
        logger.exception(f"Error sending user feedback: {e}")
        logger.info(f"Feedback from {user.first_name} (ID: {user.id}):\n\n{user_feedback}")
        await update.message.reply_text("Oops🙊, seems there's an error.\n(Either unsupported characters or an error on our side)")
        await send_critical_alert(
            context, title="Unexpected Error in sending feedback",
            context_data={"user": update.effective_user.id, "feedback":user_feedback},
            exc=e
        )
    return ConversationHandler.END


#### latest news conversation handler ####

async def show_news_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1) -> int | None:
    """
    Displays news in grid with navigation options.
    
    Args:
        update (Update): Telegram update object.
        context (Context): Context object.
    
    Returns:
        int | None: Next state or None if conversation ends.
    """
    user = update.effective_user
    news = context.user_data.get("latest_news", [])
    page = int(context.args[0]) if context.args else 1  # Default to page 1
    buttons = []

    if not news:
        news = get_news(config.settings.max_news)
        if not news:
            text = "There's no news at the moment."
            await _handle_no_news(update, text)
            return ConversationHandler.END
        context.user_data["latest_news"] = news

    total_results = len(news)
    per_page = 10  # Articles per page
    start_result = (page - 1) * per_page + 1
    end_result = min(page * per_page, total_results)
    result_summary = f"Results {start_result}-{end_result} of {total_results}"
    
    txt = f"<b>Latest News</b>\n{result_summary}\n\n"
    offset = (page - 1) * config.settings.results_per_page
    paginated_news, has_next = get_data_paginated(news, page, per_page=config.settings.results_per_page)

    for idx, article in enumerate(paginated_news):
        txt += f"{idx + 1}. {article.title}\n"
        buttons.append(InlineKeyboardButton(f"{idx+1}", callback_data=f"news_index_{offset + idx}"))

    footer_buttons = _build_footer_buttons(page, has_next)
    special_footer = [InlineKeyboardButton("Cancel", callback_data='cancel')]
    
    keyboard = build_menu(buttons, n_cols=5, footer_buttons=footer_buttons, special_footer=special_footer)
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:  # Command context
        await update.message.reply_text(txt, reply_markup=reply_markup)
    elif update.callback_query:  # Callback query context
        await _handle_message_edit(update, context, txt, reply_markup)

    return SELECTING_NEWS


async def _handle_no_news(update: Update, text):
    """Handle the case where there are no news articles."""
    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text)


def _build_footer_buttons(page: int, has_next: bool):
    """Build footer navigation buttons."""
    footer_buttons:list = []
    if page > 1:
        footer_buttons.append(InlineKeyboardButton("«", callback_data=f"news_page_{page - 1}"))
    if has_next:
        footer_buttons.append(InlineKeyboardButton("»", callback_data=f"news_page_{page + 1}"))
    return footer_buttons


async def _handle_message_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, txt, reply_markup):
    """Handle message edits for news selection or navigation."""
    msg_type = effective_message_type(update)
    if msg_type == MessageType.PHOTO:
        # If the current message is a photo, we need to delete it and send a text message
        try:
            # Delete the current photo message
            await update.callback_query.message.delete()
            # Then send the new text message
            await update.callback_query.message.reply_text(txt, reply_markup=reply_markup)
        except Exception as e:
            print(f"Error deleting message: {e}")
            # If there's an error, just edit the message (fallback to text)
            await update.callback_query.edit_message_text(txt, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(txt, reply_markup=reply_markup)


async def latest_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ The entry point command handler. """
    return await show_news_menu(update, context)


async def handle_selected_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles callback queries for navigating and news selection.
    
    Args:
        update (Update): Telegram update object.
        context (Context): Context object.

    Returns:
        None
    """
    query = update.callback_query
    await query.answer()

    if query.data.startswith("news_page_"):
        page = int(query.data.split("_")[-1])
        context.args = [str(page)]
        await show_news_menu(update, context, page)
        return SELECTING_NEWS

    if query.data.startswith("news_index_"):
        news_index = int(query.data.split("_")[-1])
        news = context.user_data.get("latest_news", [])
        selected_article = news[news_index]
        
        context.user_data["selected_news_index"] = news_index
        article_text = f"<b>{selected_article.title}</b>\n\n<i>{selected_article.summary}</i>"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 Read More", url=selected_article.link)],
            [InlineKeyboardButton("⬅️ Back", callback_data="news_page_1")]
        ])
        
        await _handle_selected_article(update, query, selected_article, article_text, keyboard)
        return SELECTING_NEWS


async def _handle_selected_article(update: Update, query, selected_article, article_text, keyboard):
    """Handle selected article display and media."""
    image_url = selected_article.image_url
    current_message_type = effective_message_type(update)  # Check the current message type
    
    # If there's an image URL, try to send the image with the article text
    if image_url:
        if current_message_type != MessageType.PHOTO:
            # If the current message type is not already a photo, send the image
            try:
                media = InputMediaPhoto(media=image_url, caption=article_text)
                await query.edit_message_media(media, reply_markup=keyboard)
            except Exception as e:
                print(f"Error sending image: {e}")
                # If there's an error with the image, fall back to sending only text
                await query.edit_message_text(article_text, reply_markup=keyboard)
        else:
            # If the message is already a photo, just edit the caption
            try:
                media = InputMediaPhoto(media=image_url, caption=article_text)
                await query.edit_message_media(media, reply_markup=keyboard)
            except Exception as e:
                print(f"Error editing image caption: {e}")
                # If there's an error with the image, fall back to sending only text
                await query.edit_message_text(article_text, reply_markup=keyboard)
    
    else:
        # If no image URL, just send the article text
        if current_message_type == MessageType.PHOTO:
            # If the current message is a photo, we need to switch to text
            await query.message.delete()  # Delete the current photo message
            await query.message.reply_text(article_text, reply_markup=keyboard)  # Send the new text message
        else:
            # If it's already text or some other type, we can just send the text
            await query.edit_message_text(article_text, reply_markup=keyboard)


@send_typing_action
async def timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Conversation timedout.")
    await update.message.reply_text("Conversation timeout reached. Goodbye!", reply_markup=ReplyKeyboardRemove())
    return

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    # Edit message to remove the buttons
    # query = update.callback_query
    # if query:
    #     await query.edit_message_text(reply_markup=None)

    user = update.message.from_user
    first_name = user.first_name
    user_id = update.effective_user.id
    logger.info(f"User: ({user_id},{first_name}) canceled the conversation.")
    print(f"Operation cancelled by ({user_id},{first_name})")
    await update.message.reply_text(
        "Operation cancelled.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END