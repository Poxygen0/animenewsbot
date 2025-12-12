from typing import Optional, List
from sqlalchemy import ForeignKey, DateTime, String, select
from sqlalchemy.orm import mapped_column, relationship, Mapped, Session
from sqlalchemy.sql import func
from .database import Base
from datetime import datetime
from config import config

from utils.logger import setup_logger

logger = setup_logger(__name__, config.paths.log_path+"/models.log")


# Table for Users
class User(Base):
    """
    Represents a Telegram user who interacts with the bot.

    Attributes:
        id (int): Telegram user ID (primary key).
        chat_id (int): The id of the current chat.
        first_name (str): The first name of the user.
        last_name (str): The last name of the user.
        username (str): The Telegram username of the user.
        is_subscribed (bool): Whether the user is subscribed for news update.
        rate_tier (str): is the user a free or premium user of the service.
        filters (dict): a dictionary of user filters to include.
        joined_at (datetime): Timestamp when the user joined the bot.
        language_code (str): User's language code.
    """
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    chat_id: Mapped[int] = mapped_column(nullable=False)
    first_name: Mapped[str] = mapped_column(nullable=True)
    last_name: Mapped[str] = mapped_column(nullable=True)
    username: Mapped[str] = mapped_column(nullable=True)
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    language_code: Mapped[Optional[str]]
    settings: Mapped["UserSettings"] = relationship("UserSettings", back_populates="user", uselist=False)
    
    @staticmethod
    def user_exists(session, user_id: int, chat_id: int, username: str=None) -> bool:
        # Class method to check if a user exists in the database by user_id or username.
        query = session.query(User)
        if user_id is not None:
            return query.filter_by(id=user_id).first() is not None
        if chat_id is not None:
            return query.filter_by(chat_id=chat_id).first() is not None
        if username is not None:
            return query.filter_by(username=username).first() is not None
        return False
    
    @staticmethod
    def add_user(session, user_id: int, chat_id: int, username: str, first_name: str, last_name: str, is_premium: bool, is_bot: bool, language_code: str) -> None:
        ''' Add a new user to the database'''
        new_user = User(
            id=user_id,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_premium=is_premium,
            is_bot=is_bot,
            language_code=language_code
        )
        session.add(new_user)
        session.commit()
        return
    
    @staticmethod
    def get_all_userIds(session) -> List:
        return [user.id for user in session.query(User.id).all()]
    
    @staticmethod
    def get_total_users(session) -> int:
        return len(session.query(User.id).all())
    
    def __repr__(self) -> str:
        return f"({self.id}, {self.chat_id}) {self.first_name} {self.last_name} {self.username}"
    

# Table for settings
class UserSettings(Base):
    __tablename__ = "user_settings"
    
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True, nullable=False)
    is_subscribed: Mapped[bool] = mapped_column(default=False)
    opted_for_channel_updates: Mapped[bool] = mapped_column(default=False)
    interval: Mapped[int] = mapped_column(default=0) # hours
    notifications_disabled: Mapped[Optional[bool]] = mapped_column(default=False)
    
    user: Mapped["User"] = relationship("User", back_populates="settings")
    
    @staticmethod
    def get_user_settings(session, user_id: int) -> Optional["UserSettings"]:
        """ Class method to get the notification info """
        return session.query(UserSettings).filter_by(user_id=user_id).first()
    
    @staticmethod
    def get_all_subscribed_users(session) -> List[int]:
        """ Class method to get all subscribed users """
        return [user.user_id for user in session.query(UserSettings.user_id).filter(UserSettings.is_subscribed == True).all()]
    
    @staticmethod
    def get_all_opted_users(session) -> List[int]:
        """ Class method to get all subscribed users """
        return [user.user_id for user in session.query(UserSettings.user_id).filter(UserSettings.opted_for_channel_updates == True).all()]
    
    @staticmethod
    def create_or_get_user_settings(session, user_id: int):
        user_settings = session.query(UserSettings).filter_by(user_id=user_id).first()
        if not user_settings:
            user_settings = UserSettings(user_id=user_id)  # default OFF notifications
            session.add(user_settings)
            session.commit()
        return user_settings
    
    @staticmethod
    def update_user_settings(session, user_id: int,
                             interval: Optional[int] = None,
                             notifications: bool = None,
                             subscribed: bool = None,
                             opted_for_channel_updates: bool = None,) -> None:
        user_settings = session.query(UserSettings).filter_by(user_id=user_id).first()
        if user_settings:
            # Update existing settings
            if interval is not None:
                user_settings.interval = interval
            if notifications is not None:
                user_settings.notifications_disabled = notifications
            if subscribed is not None:
                user_settings.is_subscribed = subscribed
            if opted_for_channel_updates is not None:
                user_settings.opted_for_channel_updates = opted_for_channel_updates
            
            session.add(user_settings)  # Mark as modified
        else:
            # Create new settings
            user_settings: UserSettings = UserSettings(user_id=user_id, interval=interval, notifications_disabled=notifications, is_subscribed=subscribed)
            session.add(user_settings)  # Add new settings
        session.commit()
        return
    
    @staticmethod
    def update_interval(session, user_id: int, interval_in: int) -> bool:
        user_settings = session.query(UserSettings).filter_by(user_id=user_id).first()
        try:
            if user_settings:
                user_settings.interval = interval_in
                session.commit()
                return True
            return False
        except Exception as e:
            logger.exception(f"Something bad happened updating interval: {e}")
    
    @staticmethod
    def update_notifications_disabled(session, user_id: int, notification_in: bool) -> bool:
        try:
            user_settings = session.query(UserSettings).filter_by(user_id=user_id).first()
            logger.debug(f"user settings: {user_settings}")
            if user_settings:
                user_settings.notifications_disabled = notification_in
                session.commit()
                logger.debug("notification setting updated")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.exception(f"Failed to update notification setting for user {user_id}: {e}")
            return False


class Channel(Base):
    """
    Represents a Telegram channel managed by the bot.

    Attributes:
        id (int): Unique channel ID (primary key).
        name (str): Name of the channel.
        username (str): Telegram username of the channel.
        added_by (int): ID of the user who added the channel.
        created_at (datetime): Timestamp when the channel was added.
    """
    __tablename__ = "channels"
    
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    username: Mapped[str] = mapped_column(nullable=True)
    added_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    added_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    
    @staticmethod
    def add_channel(session, channel_id: int, name: str, username: (str | None), user_id: int) -> None:
        '''
        Add a new channel to the database.
        
        Args:
            session (Session): Sqlalchemy session object to interact with database.
            channel_id (int): The channel's id.
            name (str): The name of the channel.
            username (str): The username of the channel if any.
            user_id (int): The id of the user adding the channel
        
        Returns:
            None: Adds channel info to the database.
        '''
        new_channel = Channel(
            id=channel_id,
            name=name,
            username=username,
            added_by=user_id
        )
        session.add(new_channel)
        session.commit()
        return
    
    @staticmethod
    def channel_exists(session, channel_id: int, name: (str|None)=None, username: (str|None)=None, user_id: (int|None)=None) -> bool:
        ''' Check if a channel already exists '''
        query = session.query(Channel)
        if channel_id is not None:
            return query.filter_by(id=channel_id).first() is not None
        if name is not None:
            return query.filter_by(name=name).first() is not None
        if username is not None:
            return query.filter_by(username=username).first() is not None
        return False
    
    @staticmethod
    def get_channel(session, channel_id: (int|None)=None, name: (str|None)=None, username: (str|None)=None):
        ''' Get a channel '''
        query = session.query(Channel)
        if channel_id is not None:
            return query.filter_by(id=channel_id).first()
        if name is not None:
            return query.filter_by(name=name).first()
        if username is not None:
            return query.filter_by(username=username).first()
        return None
    
    @staticmethod
    def get_all_user_channels(session, user_id: int) -> Optional[List['Channel']]:
        # Query all channels added by the user
        query = session.query(Channel)
        result = query.filter_by(added_by=user_id).all()
        
        # Return None if no results are found, otherwise return the result
        return result if result else None
    
    @staticmethod
    def get_all_channels(session) -> List["Channel"]:
        """
        Retrieves all Channel objects from the database.

        Args:
            session: The SQLAlchemy Session object.

        Returns:
            A list of Channel objects.
        """
        statement = select(Channel)
        return session.scalars(statement).all()
    
    @staticmethod
    def delete_channel(session, channel_id: int) -> bool:
        """Delete a channel by its ID."""
        channel = session.query(Channel).filter_by(id=channel_id).first()
        if channel:
            session.delete(channel)
            session.commit()
            return True
        return False
    
    @staticmethod
    def clear_all_channels(session, user_id: int) -> int:
        """Delete all channels for a specific user."""
        deleted_count = session.query(Channel).filter_by(user_id=user_id).delete()
        session.commit()
        return deleted_count
    
    def __repr__(self) -> str:
        return f"(ID:{self.id} Name:{self.name}) Username:{self.username} Added by:{self.added_by} Date added:{self.added_at}"


class SubscriptionLog(Base):
    __tablename__ = "subscription_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String) # "subscribed", "unsubscribed"
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    
    @staticmethod
    def log(session:Session, tg_user_id, action) -> None:
        log = SubscriptionLog(tg_user_id=tg_user_id, action=action)
        session.add(log)
        session.commit()
        return