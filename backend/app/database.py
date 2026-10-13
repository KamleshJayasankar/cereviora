"""
CEREVIORA — Database Connection and Session Management

SQLAlchemy uses an "engine" (the connection) and a "session" (a unit of work).
Every request gets its own session that is closed when the request is done.
This prevents data leaks between requests.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# connect_args is SQLite-specific: allow the same connection to be used
# across threads (FastAPI can handle multiple requests concurrently)
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.debug,  # set debug=True in .env to log all SQL
)

# SessionLocal is a factory: call it to get a new session object
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """
    All SQLAlchemy ORM models inherit from this Base class.
    This lets SQLAlchemy discover and create all tables automatically.
    """
    pass


def get_db():
    """
    FastAPI dependency that yields a database session for each request.

    The `try/finally` block guarantees the session is always closed,
    even if an exception occurs during request handling.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
