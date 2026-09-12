from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from application.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for future SQLAlchemy models."""


engine = create_engine(get_settings().sqlalchemy_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session]:
    """Yield one synchronous session and roll it back if request handling fails."""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
