"""
db.py
-----
Database engine and session management for Lodestone.

This module is the single place that knows HOW to connect to the database.
Everything else just asks for a session via the get_db() dependency.

Key SQLAlchemy concepts:
  - Engine:       The connection to the database file/server.
  - SessionLocal: A factory class that creates individual database sessions.
  - Session:      An active "conversation" with the DB — you add objects,
                  query, then commit() to save or rollback() to undo.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

# ── Engine ────────────────────────────────────────────────────────────────────
# create_engine() sets up the connection.
# connect_args={"check_same_thread": False} is required for SQLite only —
# by default SQLite disallows being accessed from multiple threads, but
# FastAPI can handle multiple requests concurrently, so we disable that check.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# ── Session factory ────────────────────────────────────────────────────────────
# sessionmaker() creates a *class* (SessionLocal) that you instantiate to get
# a session. The keyword arguments are its defaults:
#   autocommit=False → you must explicitly call session.commit() to save data.
#   autoflush=False  → SQLAlchemy won't auto-send pending changes to the DB
#                      before every query. We control this ourselves.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Declarative base ──────────────────────────────────────────────────────────
# All ORM model classes inherit from Base. SQLAlchemy uses this shared Base
# to keep a registry of every table definition, which is how create_all() knows
# what tables to create.
Base = declarative_base()


def create_tables() -> None:
    """
    Create all database tables defined in models.py.

    This is safe to call multiple times — SQLAlchemy checks if each table
    already exists before creating it (the CREATE TABLE IF NOT EXISTS pattern).
    Called once when the FastAPI app starts up.
    """
    # Import models here so their class definitions register with Base.
    # Without this import, Base.metadata has no tables to create.
    import models  # noqa: F401 — side-effect import intentional

    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency that provides a database session per request.

    Usage in a route:
        @router.post("/something")
        def my_endpoint(db: Session = Depends(get_db)):
            ...

    The 'yield' makes this a generator-based dependency:
      1. FastAPI runs code before yield → opens a session.
      2. FastAPI injects the session into the endpoint function.
      3. After the endpoint returns (or raises), FastAPI resumes here.
      4. The finally block guarantees the session is closed no matter what.

    This prevents database connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
