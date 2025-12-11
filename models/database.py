from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import config

Base = declarative_base()
db = create_engine(config.database.url, echo=config.settings.debug, future=True)
SessionLocal = sessionmaker(bind=db, autoflush=False)