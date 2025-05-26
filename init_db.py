# init_db.py
from models.database import Base, db
from models.user import User, SubscriptionLog, FavoriteAnime

def main() -> None:
    Base.metadata.create_all(bind=db)
    print("✅ Database initialized.")
    return


if __name__ == "__main__":
    main()