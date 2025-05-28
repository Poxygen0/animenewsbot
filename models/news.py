from sqlalchemy import String, Text, DateTime, desc, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from sqlalchemy.sql import func
from .database import Base
from hashlib import sha256
from typing import Optional, List, Dict

from utils.logger import setup_logger

logger = setup_logger(__name__, "./data/logs/models.log")

class NewsCache(Base):
    __tablename__ = "news_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # SHA256 of link
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(500), index=True)
    date: Mapped[Optional[str]] = mapped_column(String(50))
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    
    @classmethod
    def generate_id(cls, link: str) -> str:
        return sha256(link.encode("utf-8")).hexdigest()

    @classmethod
    def cache_articles(cls, session: Session, articles: List[Dict], max_cache: int = 500) -> int:
        new_count = 0
        for article in articles:
            article_id = cls.generate_id(article["link"])
            if session.get(cls, article_id):
                continue  # Skip if already cached

            news = cls(
                id=article_id,
                title=article["title"],
                summary=article["summary"],
                link=article["link"],
                date=article["date"],
                image_url=article.get("image_url"),
            )
            session.add(news)
            new_count += 1

        session.commit()
        
        # Trim old entries if over limit
        if max_cache:
            total = session.scalar(select(func.count()).select_from(cls))
            if total and total > max_cache:
                to_delete = total - max_cache
                oldest = session.execute(
                    select(cls.id).order_by(cls.created_at.asc()).limit(to_delete)
                ).scalars().all()
                session.query(cls).filter(cls.id.in_(oldest)).delete(synchronize_session=False)
                session.commit()

        return new_count
    
    @classmethod
    def get_latest(cls, session: Session, limit: int = 5) -> List["NewsCache"]:
        return session.execute(
            select(cls).order_by(cls.created_at.desc()).limit(limit)
        ).scalars().all()

