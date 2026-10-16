"""Database connection and session management."""

from __future__ import annotations

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from astra_agent.persistence.models import Base


class DatabaseManager:
    """Manages async database engine and sessions."""

    def __init__(self, database_url: str = "sqlite+aiosqlite:///astra_agent.db"):
        self.database_url = database_url
        self.engine: AsyncEngine = create_async_engine(
            self.database_url,
            echo=False,
            future=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_db(self) -> None:
        """Creates all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_db(self) -> None:
        """Drops all database tables (used in test teardowns)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
