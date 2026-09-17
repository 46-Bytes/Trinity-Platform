"""
Database configuration and session management.
"""
import logging
import time

from sqlalchemy import create_engine, event
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

logger = logging.getLogger(__name__)

_url = make_url(settings.DATABASE_URL)
_is_local = _url.host in (None, "localhost", "127.0.0.1", "::1")

# psycopg2 connect args. TCP keepalives stop idle connections from being
# silently dropped by NAT/firewalls between here and Render, which is what
# forces expensive (and DNS-dependent) reconnects mid-request.
_connect_args = {
    "connect_timeout": 10,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
}
if not _is_local:
    # Render's external Postgres endpoint requires TLS.
    _connect_args.setdefault("sslmode", _url.query.get("sslmode", "require"))

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=10,        # Keep connections warm so we re-dial (and re-resolve DNS) rarely
    max_overflow=10,
    pool_recycle=1800,   # Recycle before Render's idle cutoff
    pool_timeout=30,
    connect_args=_connect_args,
    echo=False,  # Disable SQL query logging (too verbose)
)

# Transient failures worth retrying: DNS blips and refused/reset dials to a
# remote host. Anything else (bad password, missing database) fails fast.
_TRANSIENT_CONNECT_ERRORS = (
    "could not translate host name",
    "name or service not known",
    "temporary failure in name resolution",
    "connection refused",
    "connection timed out",
    "server closed the connection unexpectedly",
    "connection reset by peer",
)

_CONNECT_RETRIES = 3
_CONNECT_BACKOFF = 0.5


@event.listens_for(engine, "do_connect")
def _connect_with_retry(dialect, conn_rec, cargs, cparams):
    """
    Retry new DBAPI connections on transient network/DNS errors.

    ``pool_pre_ping`` only revalidates *pooled* connections; it does nothing
    when the pool has to dial a fresh one. Without this, a single DNS hiccup
    surfaces as a 500 from whatever request happened to need a connection.
    """
    last_exc = None
    for attempt in range(1, _CONNECT_RETRIES + 1):
        try:
            return dialect.connect(*cargs, **cparams)
        except Exception as exc:  # noqa: BLE001 - re-raised below
            message = str(exc).lower()
            if not any(marker in message for marker in _TRANSIENT_CONNECT_ERRORS):
                raise
            last_exc = exc
            if attempt == _CONNECT_RETRIES:
                break
            delay = _CONNECT_BACKOFF * (2 ** (attempt - 1))
            logger.warning(
                "Transient DB connect failure (attempt %s/%s), retrying in %.1fs: %s",
                attempt, _CONNECT_RETRIES, delay, exc,
            )
            time.sleep(delay)

    logger.error("DB connect failed after %s attempts: %s", _CONNECT_RETRIES, last_exc)
    raise last_exc


# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency for getting database session.

    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
