"""
PB HERO Database Engine - Async SQLAlchemy with SQLite WAL mode.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger("pbhero.database")

_engine = None
_session_factory = None


def get_database_url() -> str:
    """Get database URL from settings."""
    settings = get_settings()
    return settings.DATABASE_URL


async def init_engine(database_url: str | None = None) -> None:
    """Initialize the database engine with WAL mode."""
    global _engine, _session_factory

    url = database_url or get_database_url()
    logger.info("Initializing database engine: %s", url.split("///")[-1] if "///" in url else url)

    _engine = create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if "sqlite" in url else {},
    )

    # Enable WAL mode for SQLite
    if "sqlite" in url:
        @event.listens_for(_engine.sync_engine, "connect")
        def _set_sqlite_wal(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    logger.info("Database engine initialized successfully")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    if _session_factory is None:
        await init_engine()
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session_direct() -> AsyncSession:
    """Get a database session directly (caller manages lifecycle)."""
    if _session_factory is None:
        await init_engine()
    return _session_factory()


async def test_connection() -> bool:
    """Test database connectivity."""
    try:
        if _engine is None:
            await init_engine()
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database connection test failed: %s", e)
        return False


async def close_engine() -> None:
    """Close the database engine."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine closed")


def get_engine():
    """Get the current engine instance."""
    return _engine
