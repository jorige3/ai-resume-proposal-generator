import os
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

DEFAULT_DB_URL = "sqlite:///data/ai_resume_proposal.db"


def get_db_url() -> str:
    """Returns the database URL from environment or default path."""
    return os.environ.get("DATABASE_URL", DEFAULT_DB_URL)


def get_engine(db_url: Optional[str] = None):
    """Creates a SQLAlchemy engine.

    Ensures the base directory exists for SQLite database files.
    """
    url = db_url or get_db_url()

    # Safely handle relative and absolute SQLite directory paths
    if url.startswith("sqlite:///"):
        db_path = url.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    connect_args = {}
    if url.startswith("sqlite"):
        # Required for SQLite multithreading compatibility (e.g. in web apps)
        connect_args["check_same_thread"] = False

    return create_engine(url, connect_args=connect_args)


# Initialize global engine and session maker
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Session:
    """Generates a new database session for operations."""
    return SessionLocal()
