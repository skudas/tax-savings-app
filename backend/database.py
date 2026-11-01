"""
Database configuration and session management.

Supports SQLite (development) or PostgreSQL (production) based on DATABASE_URL env var.
Default: sqlite:///./tax_savings.db
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base


def get_database_url() -> str:
    """Get database URL from environment or use SQLite default."""
    return os.getenv("DATABASE_URL", "sqlite:///./tax_savings.db")


def create_db_engine():
    """Create and return database engine."""
    db_url = get_database_url()

    # SQLite-specific configuration
    if db_url.startswith("sqlite"):
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            echo=os.getenv("SQL_ECHO", "false").lower() == "true"
        )
    else:
        # PostgreSQL or other databases
        engine = create_engine(
            db_url,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true"
        )

    return engine


# Create engine and session factory
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency for FastAPI to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """Drop all tables (for testing)."""
    Base.metadata.drop_all(bind=engine)
