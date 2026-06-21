"""
Database connection and session management.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from backend.models import Base

load_dotenv()

# Database configuration
DB_PATH = os.getenv("DATABASE_PATH", "data/ayurveda.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False  # Set to True for SQL debugging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables."""
    # Ensure data directory exists
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Lightweight migration for existing databases
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(suggestion_history)"))}
        if 'cooked_recipes' not in columns:
            conn.execute(text(
                "ALTER TABLE suggestion_history ADD COLUMN cooked_recipes TEXT NOT NULL DEFAULT '[]'"
            ))

        dosha_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(dosha_assignments)"))}
        if 'tendency' not in dosha_columns:
            conn.execute(text(
                "ALTER TABLE dosha_assignments ADD COLUMN tendency VARCHAR(20)"
            ))

        custom_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(custom_recipes)"))}
        if 'imbalances' not in custom_columns:
            conn.execute(text(
                "ALTER TABLE custom_recipes ADD COLUMN imbalances TEXT NOT NULL DEFAULT '[]'"
            ))

    print(f"✅ Database initialized at {DB_PATH}")


def get_db():
    """Dependency for FastAPI to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
