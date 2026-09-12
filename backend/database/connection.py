"""
AI Music Studio - Database Connection and Session Management
Configures SQLAlchemy engine, session factory, and base model class.
Default: SQLite (development).
Production-ready: Seamlessly switches to PostgreSQL via DATABASE_URL environment variable.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Project root path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Default database URL: local SQLite file
DEFAULT_DB_PATH = PROJECT_ROOT / "ai_music_studio.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")

# Engine configuration: handle SQLite-specific multithreading flags cleanly
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency for yielding database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_default_users():
    """Ensure standard ADMIN and USER demonstration accounts exist for frictionless testing."""
    from backend.database.models import User
    from backend.services.auth_service import hash_password

    db = SessionLocal()
    try:
        # 1. Standard Admin Account
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@aimusicstudio.io",
                hashed_password=hash_password("AdminPass123!"),
                role="ADMIN",
                subscription_tier="ENTERPRISE",
                is_active=True,
            )
            db.add(admin)

        # 2. Standard Studio Creator User Account
        user = db.query(User).filter(User.username == "user").first()
        if not user:
            user = User(
                username="user",
                email="user@aimusicstudio.io",
                hashed_password=hash_password("UserPass123!"),
                role="USER",
                subscription_tier="PRO",
                is_active=True,
            )
            db.add(user)

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def init_db():
    """Create all database tables on application startup, run migrations, and seed default users."""
    from backend.database import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Lightweight column migration for existing SQLite databases
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("users")]
        if "subscription_tier" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(32) DEFAULT 'FREE'"))

    seed_default_users()


# Ensure schema & column migrations are executed on import
try:
    init_db()
except Exception:
    pass