from typing import Optional
from sqlalchemy import create_engine, ForeignKey, DateTime
from sqlalchemy.orm import mapped_column, declarative_base, relationship, sessionmaker, Mapped
from sqlalchemy.sql import func
from config import DATABASE_URI, DEBUG
from datetime import datetime

Base = declarative_base()
db = create_engine(DATABASE_URI, echo=DEBUG, future=True)
SessionLocal = sessionmaker(bind=db, autoflush=False)