"""Database session factory."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from trading_lab.config import Settings


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
