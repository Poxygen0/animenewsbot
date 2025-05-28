import requests
from models.database import SessionLocal
from utils.logger import setup_logger
import time

logger = setup_logger(__name__, "./data/logs/utils.log")


# Constants
MAL_NEWS_URL = "https://myanimelist.net/news"

# Fetch and parse the MAL news page
def fetch_news_page(url, retries=30, delay=5) -> str | None:
    """Fetch a page and return the text with retries support."""
    logger.info(f"Fetching: {url}")
    for attempt in range(retries):
        try:
            response = requests.get(MAL_NEWS_URL)
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