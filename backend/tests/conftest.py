"""
Shared pytest setup for the backend test suite.

Two jobs, both of which have to happen before any `from app...` import:

1. Put `backend/` on sys.path so `app` is importable when pytest is run from
   anywhere.
2. Make `app.config.Settings` constructible without a .env file. Importing
   anything under `app.services` pulls in app/services/__init__.py ->
   AuthService -> Settings, which has ten required fields and would otherwise
   raise ValidationError at import time on a machine with no .env.

The stubs are only injected when there is no .env to read, so a normal dev
checkout keeps using its real configuration and nothing here can shadow it.
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Settings fields with no default. Kept in sync with app/config.py by hand;
# a new required field there will surface here as a ValidationError on import.
_REQUIRED_SETTINGS = {
    "DATABASE_URL": "sqlite:///test.db",
    "AUTH0_DOMAIN": "test.auth0.com",
    "AUTH0_CLIENT_ID": "test-client-id",
    "AUTH0_CLIENT_SECRET": "test-client-secret",
    "AUTH0_AUDIENCE": "https://test.api",
    "AUTH0_MANAGEMENT_API_AUDIENCE": "https://test.auth0.com/api/v2/",
    "AUTH0_MANAGEMENT_CLIENT_ID": "test-mgmt-client-id",
    "AUTH0_MANAGEMENT_CLIENT_SECRET": "test-mgmt-client-secret",
    "SECRET_KEY": "test-secret-key",
    "ANTHROPIC_API_KEY": "sk-ant-test",
}

if not os.path.exists(os.path.join(BACKEND_DIR, ".env")):
    for _key, _value in _REQUIRED_SETTINGS.items():
        os.environ.setdefault(_key, _value)


# ----------------------------------------------------------------------
# Database fixtures
#
# Everything below is lazy: the engine is built inside a fixture, so pure
# unit tests that never request `db_session` open no connection at all.
#
# SQLite is not usable here. The two deliverable tables do build on it, but
# `server_default='false'` is stored as the literal string 'false', which
# SQLAlchemy reads back as Python True - every freshly materialized row would
# report complete and deleted. Tests run against real Postgres instead.
#
# They run against the local database in DATABASE_URL. That is safe because
# nothing here ever commits: db_session holds an outer transaction and joins
# the Session to it as a savepoint, so a service's own db.commit() only issues
# RELEASE SAVEPOINT and teardown discards the lot. Set TEST_DATABASE_URL to
# point somewhere else if you would rather keep test runs off your dev data.
#
# The database must be migrated to this branch's head:  alembic upgrade head
# ----------------------------------------------------------------------
import uuid  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

_SKIP_REASON = (
    "Database has no engagement_module_deliverable table. Migrate it first:\n"
    "    cd backend && alembic upgrade head\n"
    "Or set TEST_DATABASE_URL to a database that is already migrated."
)


@pytest.fixture(scope="session")
def engine():
    """
    Engine for the test database: TEST_DATABASE_URL if set, else DATABASE_URL.

    Skips the DB tests with instructions when the target has not been migrated,
    rather than failing 30 times with UndefinedTable.
    """
    from app.config import settings

    url = os.environ.get("TEST_DATABASE_URL") or settings.DATABASE_URL
    eng = create_engine(url)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1 FROM engagement_module_deliverable LIMIT 0"))
    except Exception:
        eng.dispose()
        pytest.skip(_SKIP_REASON, allow_module_level=True)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    """
    A Session that can never commit anything to the real database.

    The connection holds an outer transaction and the Session joins it with
    join_transaction_mode="create_savepoint", so a service calling db.commit()
    only issues RELEASE SAVEPOINT. Rolling the outer transaction back in
    teardown discards every row the test created.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def test_user(db_session):
    """Throwaway user, discarded with the transaction."""
    from app.models.user import User

    user = User(email=f"deliverable-test-{uuid.uuid4()}@example.test")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def test_engagement(db_session, test_user):
    """Throwaway value_builder engagement, discarded with the transaction."""
    from app.models.engagement import Engagement

    engagement = Engagement(
        engagement_name="Deliverable test engagement",
        primary_advisor_id=test_user.id,
        tool="value_builder",
    )
    db_session.add(engagement)
    db_session.flush()
    return engagement
