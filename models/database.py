from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DATABASE_URI, DEBUG

Base = declarative_base()
db = create_engine(DATABASE_URI, echo=DEBUG, future=True)
SessionLocal = sessionmaker(bind=db, autoflush=False)