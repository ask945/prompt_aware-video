import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Build URL with properly encoded password to handle special chars like @
_raw_url = os.getenv("DATABASE_URL", "")
_DB_USER = os.getenv("DB_USER", "")
_DB_PASS = os.getenv("DB_PASS", "")
_DB_HOST = os.getenv("DB_HOST", "localhost")
_DB_PORT = os.getenv("DB_PORT", "5433")
_DB_NAME = os.getenv("DB_NAME", "video_ai")

if _DB_USER and _DB_PASS:
    DATABASE_URL = (
        f"postgresql+psycopg2://{quote_plus(_DB_USER)}:{quote_plus(_DB_PASS)}"
        f"@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"
    )
elif _raw_url:
    DATABASE_URL = _raw_url
else:
    raise RuntimeError("DATABASE_URL or DB_USER+DB_PASS must be set in .env.local")

# Engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# Session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
