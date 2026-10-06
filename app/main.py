"""
PB HERO Application Main Entry Point.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import uvicorn

from app.bot.client import PBHeroBot
from app.config import get_settings
from app.dashboard.app import create_dashboard_app
from app.database.engine import close_engine, get_session_direct, init_engine
from app.database.models import Base
from app.database.repositories import (
    AdminUserRepo,
    AutomodRuleRepo,
    PolicyProfileRepo,
    WarningEscalationRepo,
    YouTubeTemplateRepo,
    ServerGreetingSettingsRepo,
    ServerInviteSettingsRepo,
)
from app.dashboard.auth import hash_password
from app.logging_config import setup_logging
from app.runtime_state import (
    BotState,
    clear_bot_instance,
    get_bot_instance,
    set_bot_instance,
    set_bot_state,
)

logger = logging.getLogger("pbhero.main")


async def init_database(create_admin_user: bool = True) -> None:
    """Initialize SQLite database directory, create tables, and populate defaults."""
    settings = get_settings()
    # Ensure data directory exists
    if "sqlite" in settings.DATABASE_URL:
        db_path = settings.DATABASE_URL.split("///")[-1]
        parent_dir = Path(db_path).parent
        parent_dir.mkdir(parents=True, exist_ok=True)

    await init_engine()
    from app.database.engine import get_engine
    engine = get_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _ensure_free_game_columns(sync_conn):
            from sqlalchemy import inspect, text
            inspector = inspect(sync_conn)
            if "free_game_offers" in inspector.get_table_names():
                existing_cols = {c["name"] for c in inspector.get_columns("free_game_offers")}
                if "canonical_claim_url" not in existing_cols:
                    sync_conn.execute(text("ALTER TABLE free_game_offers ADD COLUMN canonical_claim_url VARCHAR(1024)"))
                if "claim_url_status" not in existing_cols:
                    sync_conn.execute(text("ALTER TABLE free_game_offers ADD COLUMN claim_url_status VARCHAR(32) DEFAULT 'VALID'"))
                if "validated_at" not in existing_cols:
                    sync_conn.execute(text("ALTER TABLE free_game_offers ADD COLUMN validated_at DATETIME"))

        await conn.run_sync(_ensure_free_game_columns)

    # Initialize default policy profiles (15 text + 10 voice presets = 25 built-in presets)
    session = await get_session_direct()
    try:
        profiles = await PolicyProfileRepo.get_all(session)
        builtin_count = sum(1 for p in profiles if getattr(p, "is_builtin", False))
        if not profiles or builtin_count < 25:
            await PolicyProfileRepo.create_defaults(session)
            await session.commit()
            logger.info("Created or updated default policy profiles (25 presets)")

        # Initialize default automod rules
        await AutomodRuleRepo.create_defaults(session)
        await session.commit()

        # Initialize default warning escalation ladder
        await WarningEscalationRepo.create_defaults(session)
        await session.commit()

        # Initialize default YouTube notification templates
        await YouTubeTemplateRepo.create_defaults(session)
        await session.commit()

        # Initialize default Server Greeting and Invite settings if guild configured
        if settings.DISCORD_GUILD_ID:
            await ServerGreetingSettingsRepo.get_or_create(session, settings.DISCORD_GUILD_ID)
            await ServerInviteSettingsRepo.get_or_create(session, settings.DISCORD_GUILD_ID)
            await session.commit()

        # Initialize admin user if configured in environment
        if create_admin_user and settings.ADMIN_USERNAME:
            existing = await AdminUserRepo.get_by_username(session, settings.ADMIN_USERNAME)
            if not existing and (settings.ADMIN_PASSWORD_HASH or os.getenv("ADMIN_PASSWORD")):
                pwd = os.getenv("ADMIN_PASSWORD")
                pwd_hash = settings.ADMIN_PASSWORD_HASH or (hash_password(pwd) if pwd else None)
                if pwd_hash:
                    await AdminUserRepo.create(session, settings.ADMIN_USERNAME, pwd_hash)
                    await session.commit()
                    logger.info("Admin user '%s' created", settings.ADMIN_USERNAME)
    finally:
        await session.close()


async def run_server() -> None:
    """Run bot and dashboard concurrently."""
    setup_logging()
    settings = get_settings()
    logger.info("Starting PB HERO Personal Discord Bot...")

    await init_database()

    # Create dashboard app
    app = create_dashboard_app()
    server_config = uvicorn.Config(
        app=app,
        host=settings.DASHBOARD_HOST,
        port=settings.DASHBOARD_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=False,
    )
    server = uvicorn.Server(server_config)

    bot: Optional[PBHeroBot] = None
    if settings.DISCORD_BOT_TOKEN:
        bot = PBHeroBot(settings)
        set_bot_instance(bot)
        set_bot_state(BotState.STARTING)

    async def _run_bot_safe():
        backoff = 3
        max_backoff = 60
        while bot and not bot.is_closed():
            try:
                logger.info("Connecting Discord bot to gateway (reconnect=True)...")
                set_bot_state(BotState.STARTING)
                await bot.start(settings.DISCORD_BOT_TOKEN, reconnect=True)
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                set_bot_state(BotState.ERROR)
                logger.error(
                    "Discord bot connection terminated: %s. Reconnecting in %ds...",
                    e,
                    backoff,
                )
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    break
                backoff = min(backoff * 2, max_backoff)

    tasks = [asyncio.create_task(server.serve())]
    if bot:
        tasks.append(asyncio.create_task(_run_bot_safe()))
    else:
        set_bot_state(BotState.STOPPED)
        logger.warning("DISCORD_BOT_TOKEN is not configured; running dashboard only")

    try:
        await asyncio.gather(*tasks)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutting down services...")
    finally:
        set_bot_state(BotState.STOPPING)
        if bot and not bot.is_closed():
            await bot.close()
        clear_bot_instance()
        server.should_exit = True
        await close_engine()
        logger.info("PB HERO stopped")


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="PB HERO Personal Discord Bot")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "init-db", "create-admin"])
    parser.add_argument("--username", help="Admin username")
    parser.add_argument("--password", help="Admin password")
    args = parser.parse_args()

    if args.command == "init-db":
        setup_logging()
        asyncio.run(init_database(create_admin_user=True))
        print("Database initialized successfully.")
    elif args.command == "create-admin":
        setup_logging()
        username = args.username or input("Username: ")
        password = args.password or input("Password: ")
        async def _create():
            await init_engine()
            session = await get_session_direct()
            try:
                existing = await AdminUserRepo.get_by_username(session, username)
                pwd_hash = hash_password(password)
                if existing:
                    await AdminUserRepo.update_password(session, username, pwd_hash)
                    print(f"Password updated for admin user '{username}'.")
                else:
                    await AdminUserRepo.create(session, username, pwd_hash)
                    print(f"Admin user '{username}' created successfully.")
                await session.commit()
            finally:
                await session.close()
                await close_engine()
        asyncio.run(_create())
    else:
        asyncio.run(run_server())


if __name__ == "__main__":
    main()
