import requests
import html
import os
import traceback
from datetime import datetime, timezone

from telegram.ext import ContextTypes
from telegram import error

from PIL import Image
from io import BytesIO
from bs4 import BeautifulSoup
from config import config
from models.database import SessionLocal
from models.user import Channel
from models.news import NewsCache
from telegram import InlineKeyboardButton
from utils.logger import setup_logger
from typing import List, Dict, Optional, Union, Tuple
import time
import re
from urllib.parse import urlparse, urlunparse

logger = setup_logger(__name__, config.paths.log_path+"/utils.log")


def get_channels() -> list | None:
    ''' Get all channels in the db '''
    
    with SessionLocal() as session:
        channels = Channel.get_all_channels(session)
    return channels

def get_user_channels(user_id: int) -> list | None:
    ''' Get the channels added by the user_id'''
    
    with SessionLocal() as session:
        user_channels = Channel.get_all_channels(session)
    return user_channels

def escape_html(text: str) -> str:
    """Escapes HTML reserved characters in text."""
    return html.escape(text)

def is_owner(user_id: int) -> bool:
    """ Checks if the user is the bot owner """
    return user_id == config.bot.owner_id

def get_clean_image_url(link:str) -> str:
    """
    Extracts the image URL from the provided link and removes any query parameters.
    
    Args:
        link (str): The image link with queries
    
    Returns:
        str: Cleaned image URL without query parameters
    """
    parsed_url = urlparse(link)
    
    # Remove size-related segments like /r/100x156
    path_parts = parsed_url.path.split('/')
    
    # Keep only the part of the path after /s/ (size is usually indicated by /r/ or similar)
    if 'r' in path_parts:
        # Look for the part "/r/100x156" and remove it if it matches the "WIDTHxHEIGHT" format
        if len(path_parts) > 2 and path_parts[1] == 'r':
            size_part = path_parts[2]
            if re.match(r'\d+x\d+', size_part):  # Check if it's a valid WIDTHxHEIGHT format (e.g., 100x156)
                path_parts = path_parts[:1] + path_parts[3:]  # Remove the /r/100x156 part
    
    # Reassemble the URL
    cleaned_path = '/'.join(path_parts)
    cleaned_url = urlunparse(parsed_url._replace(path=cleaned_path, query=""))
    
    #cleaned_url = urlunparse(parsed_url._replace(query="")) # Remove the query part
    return cleaned_url

# Fetch and parse the MAL news page
def fetch_news_page(url, retries=30, delay=5) -> str | None:
    """Fetch a page and return the text with retries support."""
    logger.info(f"Fetching: {url}")
    for attempt in range(retries):
        try:
            response = requests.get(url)
            response.raise_for_status()
            logger.info(f"Successfully fetched: {url}")
            return response.text
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                logger.exception(f"All {retries} attempts failed for: {url}")
                return

def extract_news_articles(page_html: str) -> List[Dict[str, Optional[str]]]:
    ''' For parsing and extracting the news content '''
    soup = BeautifulSoup(page_html, 'lxml')
    articles = []

    for article in soup.find_all('div', attrs={'class':'news-unit'}):
        title_tag = article.find('p', class_='title')
        if not title_tag:
            logger.info(f"Skipping article with no title: {article}")
            continue
        title = title_tag.get_text(strip=True)
        link = title_tag.find('a')['href']
        summary = article.find('div', class_='text').get_text(strip=True) if article.find('div', class_='text') else ''
        date_str = article.find('p', class_='info').next_element.get_text(strip=True,)[:-2] if article.find('p', class_='info') else ''
        # date_str_text = date_str.find(string=True, recursive=False)
        image_url_tag = article.find('a', class_='image-link') if article.find('a', class_='image-link') else None
        image_url = get_clean_image_url(image_url_tag.find('img')['src']) if image_url_tag else None
        logger.info(f"Done extracting article info for: {title}")

        articles.append({
            'title': title,
            'summary': summary,
            'link': link,
            'date': date_str,
            'image_url': image_url
        })
    logger.info("Done extracting all articles for MAL site")
    return articles

def get_channels() -> list | None:
    ''' Get all channels in the db '''
    
    with SessionLocal() as session:
        channels = Channel.get_all_channels(session)
    return channels

def get_user_channels(user_id: int) -> list | None:
    ''' Get the channels added by the user_id'''
    
    with SessionLocal() as session:
        user_channels = Channel.get_all_user_channels(session, user_id)
    return user_channels

def get_news(limit:int = 5) -> list | None:
    ''' Get the latest news '''
    
    with SessionLocal() as session:
        news = NewsCache.get_latest(session, limit)
    return news

def build_menu(
    buttons: List[InlineKeyboardButton],
    n_cols: int,
    header_buttons: Union[InlineKeyboardButton, List[InlineKeyboardButton]]=None,
    footer_buttons: Union[InlineKeyboardButton, List[InlineKeyboardButton]]=None,
    special_footer: Union[InlineKeyboardButton, List[InlineKeyboardButton]]=None,
) -> List[List[InlineKeyboardButton]]:
    """
    Arranges buttons into a grid.

    Args:
        buttons (list): List of InlineKeyboardButton objects.
        n_cols (int): Number of columns in the grid.
        header_buttons(list): Buttons to add as a header row.
        footer_buttons (list): Buttons to add as a footer row.
        special_footer(list): Buttons after the footer row.

    Returns:
        list: A grid layout of buttons.
    """
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons if isinstance(header_buttons, list) else [header_buttons])
    if footer_buttons:
        menu.append(footer_buttons if isinstance(footer_buttons, list) else [footer_buttons])
    if special_footer:
        menu.append(special_footer if isinstance(special_footer, list) else [special_footer])
    return menu

# Mock function to get paginated data
def get_data_paginated(data:list, page:int=1, per_page:int=6):
    """
    Fetches channels for a user with pagination.

    Args:
        data (list): A list of available data.
        page (int): The current page number.
        per_page (int): Number of data per page.

    Returns:
        tuple[list[dict], bool]: A list of data and a flag if there's a next page.
    """
    # all_channels = [
    #     {"id": 1, "name": "Channel 1"},
    #     {"id": 2, "name": "Channel 2"},
    #     {"id": 3, "name": "Channel 3"},
    #     {"id": 4, "name": "Channel 4"},
    #     {"id": 5, "name": "Channel 5"},
    #     {"id": 6, "name": "Channel 6"},
    #     {"id": 7, "name": "Channel 7"},
    # ]
    start = (page - 1) * per_page
    end = start + per_page
    has_next = end < len(data)
    data = data[start:end]
    return data, has_next

def format_uptime(seconds: float) -> str:
    seconds = int(seconds)

    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    weeks, days = divmod(days, 7)

    parts = []
    if weeks: parts.append(f"{weeks}w")
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if sec: parts.append(f"{sec}s")

    return " ".join(parts) if parts else "0s"

def resize_and_process_image(
    image_url: str, 
    max_size: Tuple[int, int] = (800, 800)
) -> BytesIO:
    """
    Downloads an image from a URL, resizes it, and returns the image data in a BytesIO object.
    
    Args:
        image_url: The URL of the image to process.
        max_size: A tuple (width, height) for the maximum dimensions.
        
    Returns:
        A BytesIO object containing the processed image data, or None on failure.
    """
    try:
        # Download the image data from the URL
        response = requests.get(image_url, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        # Open the image using Pillow from the bytes data
        image_data = BytesIO(response.content)
        img = Image.open(image_data)

        # Preserve aspect ratio while resizing
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save the resized image to a new BytesIO object
        output_data = BytesIO()
        img.save(output_data, format=img.format)
        output_data.seek(0) # Rewind the buffer to the beginning

        return output_data
    
    except (requests.exceptions.RequestException, IOError) as e:
        logger.exception(f"Error processing image from {image_url}: {e}")
        return None

def format_short_traceback(exc: Exception) -> str:
    """
    Formats an exception's traceback, stripping directory paths from file names.
    Returns the traceback string.
    """
    if exc.__traceback__ is None:
        return f"Exception: {type(exc).__name__}: {exc}"

    # 1. Get the list of traceback frames
    formatted_list = traceback.extract_tb(exc.__traceback__)
    
    short_traceback = []
    
    # 2. Iterate through frames and modify the filename
    for frame in formatted_list:
        # Use os.path.basename to strip the directory path
        short_filename = os.path.basename(frame.filename)
        
        # Create a new FrameSummary with the shortened filename
        # This is necessary because traceback.format_list expects this structure
        new_frame = traceback.FrameSummary(
            filename=short_filename,
            lineno=frame.lineno,
            name=frame.name,
            line=frame.line
        )
        short_traceback.append(new_frame)

    # 3. Format the list back into standard traceback lines
    formatted_lines = traceback.format_list(short_traceback)
    
    # 4. Add the exception type and message at the end
    formatted_lines.append(f"{type(exc).__name__}: {exc}\n")
    
    return "".join(formatted_lines)

async def send_critical_alert(
    context: ContextTypes.DEFAULT_TYPE, 
    title: str, 
    context_data: dict, 
    exc: Optional[Exception] = None
) -> None:
    """
    Sends a structured, high-priority alert to the dedicated admin log channel.
    """
    channel_id = config.bot.log_channel_id
    
    if channel_id == 0 or channel_id is None:
        logger.error(f"Critical Alert FAILED: BOT__LOG_CHANNEL_ID is not set. Title: {title}")
        return

    message_parts = [
        f"🚨 <b>CRITICAL ALERT: {escape_html(title)}</b> 🚨",
        f"• 🤖<b>Bot:</b> `{config.bot.username}`\n",
        f"<b>Timestamp:</b> <code>{datetime.now(timezone.utc).isoformat()}</code>",
        f"<b>Context Data:</b>",
    ]

    # Add structured context data
    for key, value in context_data.items():
        escaped_value = escape_html(str(value))
        message_parts.append(f"  - <code>{escape_html(key)}</code>: <code>{escaped_value}</code>")

    # Add traceback if an exception is provided
    if exc:
        traceback_str = format_short_traceback(exc)
        # traceback_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        escaped_traceback = escape_html(traceback_str)
        message_parts.append(
            "\n--- <b>Traceback</b> ---\n"
            f"<pre>{escaped_traceback[:3500]}... (truncated)</pre>"
        )

    alert_message = "\n".join(message_parts)

    try:
        # Send the message using HTML parse mode (as configured in Defaults)
        await context.bot.send_message(
            chat_id=channel_id,
            text=alert_message,
        )
    except error.TelegramError as e:
        logger.critical(f"FATAL: Could not send critical alert to admin channel {channel_id}: {e}")