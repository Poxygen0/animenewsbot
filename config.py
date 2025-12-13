from datetime import timedelta
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class BotConfig(BaseModel):
    """Configuration for the Telegram bot client."""
    token: str
    owner_id: int
    username: str
    log_channel_id: Optional[int]
    timeout: int = 300

class DatabaseConfig(BaseModel):
    url: str

class PathsConfig(BaseModel):
    """Configuration for file paths."""
    data_dir: str = "data/"
    database_dir: str = "data/database"
    log_path: str = "data/logs"
    log_file: str = "bot.log"
    
    def ensure_directories(self):
        for path in [self.data_dir, self.log_path, self.database_dir]:
            os.makedirs(path, exist_ok=True)


class LoggingConfig(BaseModel):
    """Configuration for logging settings."""
    log_to_console: bool = True
    log_max_bytes: int = 5 * 1024 * 1024
    log_backup_count: int = 4
    noisy_loggers: List[str] = Field(default_factory=lambda: [
        "httpx",
        "httpcore",
        "apscheduler",
        "urllib3",
    ])

class SettingsConfig(BaseModel):
    """General application settings."""
    debug: bool = True
    overall_max_rate: int = 25      # Max 30 requests per second across all chats
    overall_time_period: int = 1
    group_max_rate: int = 15        # Max 20 requests per minute in a single group
    group_time_period: int = 60
    results_per_page: int = 10
    max_news: int = 50
    news_expiration_time: timedelta = timedelta(days=5)
    interval_in_secs: int = 10 * 60 # Minutes
    mal_news_url: HttpUrl = "https://myanimelist.net/news"
    default_timezone: str = 'UTC'

class AppConfig(BaseSettings):
    """Main application configuration, loaded from environment variables and .env file."""
    bot: BotConfig
    database: DatabaseConfig
    paths: PathsConfig = Field(default_factory=PathsConfig)
    settings: SettingsConfig = Field(default_factory=SettingsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",  # Use double-underscore for nested env vars
        env_file_encoding="utf-8",
        extra='forbid'
    )
    
    def initialize(self):
        # Ensure all directories exist
        self.paths.ensure_directories()



# The globally accessible configuration object
try:
    config = AppConfig()
    config.initialize()
except Exception as e:
    print(f"Error loading configuration: {e}")
    import sys
    sys.exit(1)