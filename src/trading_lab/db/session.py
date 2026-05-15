"""Database session factory."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from trading_lab.config import Settings
from trading_lab.db.models import Base


def ensure_schema(database_url: str) -> None:
    """Create tables when missing (SQLite dev convenience)."""
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)


@contextmanager
def managed_session(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Provide a session with commit on success and rollback on error."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory bound to ``settings.database_url``."""
    engine = create_engine(settings.database_url, future=True)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


def session_scope(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Yield a session and commit or rollback on exit."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
