"""
Pytest configuration and fixtures for PB HERO Personal Discord Bot.
"""

import asyncio
import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set testing environment variables before importing app
os.environ["DISCORD_BOT_TOKEN"] = "test_bot_token_abc123"
os.environ["DISCORD_GUILD_ID"] = "123456789012345678"
os.environ["ADMIN_USERNAME"] = "testadmin"
os.environ["ADMIN_PASSWORD_HASH"] = ""
os.environ["SESSION_SECRET"] = "test_secret_key_0123456789abcdef0123456789abcdef"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.config import get_settings
from app.database.models import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for session-scoped async fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncSession:
    """Provide a clean transactional database session."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
