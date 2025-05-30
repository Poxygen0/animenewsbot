import requests
from bs4 import BeautifulSoup
from models.database import SessionLocal
from utils.logger import setup_logger
from typing import List, Dict, Optional
import time

logger = setup_logger(__name__, "./data/logs/utils.log")


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
        image_url = image_url_tag.find('img')['srcset'] if image_url_tag else None
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