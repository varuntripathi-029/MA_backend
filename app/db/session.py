import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

# pool_pre_ping: SQLAlchemy tests a pooled connection with a lightweight
# query before handing it out, discarding and replacing it if it's gone
# stale (e.g. the DB dropped it during a long idle gap) instead of handing
# the caller a dead connection.
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Managed free-tier Postgres (Neon, etc.) suspends its compute after
# inactivity; the first connection attempt to a suspended endpoint can fail
# outright rather than transparently waiting for it to wake, which otherwise
# surfaces as a bare 500 to whichever request happens to arrive first.
_CONNECT_RETRIES = 4
_CONNECT_RETRY_DELAY_S = 2.0


async def _ensure_connected(session: AsyncSession) -> None:
    for attempt in range(1, _CONNECT_RETRIES + 1):
        try:
            await session.execute(text("SELECT 1"))
            return
        except OperationalError:
            if attempt == _CONNECT_RETRIES:
                raise
            logger.warning(
                "DB connection attempt %d/%d failed, retrying (database may be waking up)",
                attempt,
                _CONNECT_RETRIES,
            )
            await session.rollback()
            await asyncio.sleep(_CONNECT_RETRY_DELAY_S)


@asynccontextmanager
async def resilient_session() -> AsyncGenerator[AsyncSession, None]:
    """Use this instead of AsyncSessionLocal() directly anywhere a fresh
    session is opened outside the get_db() FastAPI dependency (e.g. the scan
    background task) — same retry-through-a-sleeping-DB behavior."""
    session = AsyncSessionLocal()
    try:
        await _ensure_connected(session)
        yield session
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with resilient_session() as session:
        yield session
