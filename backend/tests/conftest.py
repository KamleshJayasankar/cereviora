"""
CEREVIORA — pytest configuration and shared fixtures

What is a fixture?
  A fixture is a function that sets something up before a test runs
  and tears it down after. pytest automatically detects fixtures with
  the @pytest.fixture decorator and injects them into tests by name.

Why an isolated test database?
  We NEVER want tests to touch the real cereviora.db file.
  If we did, test data would contaminate the development database
  and tests would depend on each other's execution order.

  We use SQLite :memory: — an in-memory database that disappears when
  the connection closes.

The StaticPool trick (why it's needed):
  SQLite :memory: databases are PER-CONNECTION. If connection A creates
  a table and connection B tries to use it, B sees an empty database —
  "no such table". SQLAlchemy's StaticPool forces ALL sessions to share
  ONE underlying connection, so every operation sees the same tables and
  data.

How does the dependency override work?
  FastAPI's `app.dependency_overrides` is a dict you can populate
  to swap out any Depends(something) for a replacement function.
  We replace `get_db` (which normally opens cereviora.db) with a
  function that opens the shared in-memory DB instead.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db

# ── Shared in-memory SQLite using StaticPool ───────────────────────────────────
# StaticPool: all SQLAlchemy connections share a single underlying
# sqlite3 connection object — so create_all() and every session see the
# same in-memory database.
SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"   # :memory: via StaticPool

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """
    Replacement for the real get_db dependency.
    Returns sessions connected to the shared in-memory test database.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def reset_test_db():
    """
    Before every test: create all tables in the shared in-memory DB.
    After  every test: drop all tables (wipes all data).

    autouse=True means this fixture runs for every test automatically.
    """
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client():
    """
    A TestClient with the database dependency swapped for the in-memory
    test database. All HTTP calls through this client use the test DB.
    """
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def db_session():
    """Direct database session for inspecting underlying tables and rows."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

