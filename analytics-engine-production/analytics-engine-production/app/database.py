"""Database engine and session setup."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.resolved_database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize only engine-owned tables on PostgreSQL.

    On SQLite, create all local tables because it is used as the demo/test
    database. On PostgreSQL/Supabase, cameras and plate_events already exist
    and are treated as production-owned tables.
    """
    from . import models

    if settings.is_sqlite:
        Base.metadata.create_all(bind=engine)
    else:
        models.TrafficBaseline.__table__.create(bind=engine, checkfirst=True)
