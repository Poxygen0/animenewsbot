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
    is_subscribed: Mapped[bool] = mapped_column(default=False)

    user: Mapped["User"] = relationship("User", back_populates="settings")
    
    @classmethod
    def get_user_settings(cls, session, user_id: int) -> Optional["UserSettings"]:
        """ Class method to get the notification info """
        return session.query(cls).filter_by(user_id=user_id).first()
    
    @classmethod
    def update_user_settings(cls, session, user_id: int,
                             interval: Optional[int] = None,
                             notifications: bool = None,
                             subscribed: bool = None) -> None:
        user_settings = session.query(cls).filter_by(user_id=user_id).first()
        if user_settings:
            # Update existing settings
            if interval is not None:
                user_settings.interval = interval
            if notifications is not None:
                user_settings.notifications_disabled = notifications
            if subscribed is not None:
                user_settings.is_subscribed = subscribed
            
            session.add(user_settings)  # Mark as modified
        else:
            # Create new settings
            user_settings: UserSettings = cls(user_id=user_id, interval=interval, notifications_disabled=notifications, is_subscribed=subscribed)
            session.add(user_settings)  # Add new settings
        session.commit()
        return


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

