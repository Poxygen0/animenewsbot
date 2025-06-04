from typing import Optional
from sqlalchemy import create_engine, ForeignKey, DateTime, String, JSON
from sqlalchemy.orm import mapped_column, declarative_base, relationship, sessionmaker, Mapped, Session
from sqlalchemy.sql import func
from .database import Base, SessionLocal
from datetime import datetime


# Table for Users
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    chat_id: Mapped[int] = mapped_column(nullable=False)
    first_name: Mapped[str] = mapped_column(nullable=True)
    last_name: Mapped[str] = mapped_column(nullable=True)
    username: Mapped[str] = mapped_column(nullable=True)
    is_subscribed: Mapped[bool] = mapped_column(default=False)
    rate_tier: Mapped[str] = mapped_column(default="free")  # "free", "premium"
    filters: Mapped[dict] = mapped_column(JSON, default={})
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    language_code: Mapped[Optional[str]]
    settings: Mapped["UserSettings"] = relationship("UserSettings", back_populates="user", uselist=False)
    

# Table for settings
class UserSettings(Base):
    __tablename__ = "user_settings"
    
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True, nullable=False)
    interval: Mapped[int] = mapped_column(default=0) # hours
    notifications_disabled: Mapped[Optional[bool]] = mapped_column(default=False)
    
    user: Mapped["User"] = relationship("User", back_populates="settings")


class SubscriptionLog(Base):
    __tablename__ = "subscription_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String) # "subscribed", "unsubscribed"
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    
    @classmethod
    def log(cls, session:Session, tg_user_id, action) -> None:
        log = cls(tg_user_id=tg_user_id, action=action)
        session.add(log)
        session.commit()
        return


class FavoriteAnime(Base):
    __tablename__ = "favorite_anime"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String)
    added_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())

