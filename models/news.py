from sqlalchemy import String, Text, DateTime, desc, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from sqlalchemy.sql import func
from .database import Base
from hashlib import sha256
from typing import Optional, List, Dict
from config import config

from utils.logger import setup_logger

logger = setup_logger(__name__, config.paths.log_path+"/models.log")


class NewsCache(Base):
    __tablename__ = "news_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # SHA256 of link
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(500), index=True)
    date: Mapped[Optional[str]] = mapped_column(String(50))
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    
    @staticmethod
    def generate_id(link: str) -> str:
        return sha256(link.encode("utf-8")).hexdigest()

    @staticmethod
    def cache_articles(session: Session, articles: List[Dict], max_cache: int = 3000) -> tuple:
        new_count = 0
        new_news = []
        for article in articles:
            article_id = NewsCache.generate_id(article["link"])
            if session.get(NewsCache, article_id):
                continue  # Skip if already cached

            news = NewsCache(
                id=article_id,
                title=article["title"],
                summary=article["summary"],
                link=article["link"],
                date=article["date"],
                image_url=article.get("image_url"),
            )
            session.add(news)
            new_news.append(article)
            new_count += 1

        session.commit()
        
        # Trim old entries if over limit
        if max_cache:
            total = session.scalar(select(func.count()).select_from(NewsCache))
            if total and total > max_cache:
                to_delete = total - max_cache
                oldest = session.execute(
                    select(NewsCache.id).order_by(NewsCache.created_at.asc()).limit(to_delete)
                ).scalars().all()
                session.query(NewsCache).filter(NewsCache.id.in_(oldest)).delete(synchronize_session=False)
                session.commit()

        return new_count, new_news
    
    @staticmethod
    def get_latest(session: Session, limit: int = 10) -> List["NewsCache"]:
        return session.execute(
            select(NewsCache).order_by(NewsCache.created_at.desc()).limit(limit)
        ).scalars().all()

