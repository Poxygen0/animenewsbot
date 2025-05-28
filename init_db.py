# init_db.py
from models.database import Base, db
from models.user import User, SubscriptionLog, FavoriteAnime
from models.news import NewsCache
from utils.logger import setup_logger

logger = setup_logger(__name__, "./data/logs/models.log")

def main() -> None:
    Base.metadata.create_all(bind=db)
    logger.info("✅ Database initialized.")
    return


if __name__ == "__main__":
    main()