"""Shared test fixtures.

DB-touching tests run against a real local Postgres ("mxrating_test") since
the models use JSONB and asyncpg — there's no in-memory substitute that
speaks the same dialect. Each test's rows are cleaned up afterward (delete
from Project, which cascades to everything) rather than relying on
transaction rollback, since the background-task code under test opens its
own sessions independent of whatever session a test holds.
"""

import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.session import Base
from app.models import Project

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:NewStrongPassword@127.0.0.1:5432/mxrating_test"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    import app.models  # noqa: F401  registers every model on Base.metadata

    # NullPool: FastAPI's TestClient runs the ASGI app in a separate thread
    # with its own event loop, so a pooled asyncpg connection opened under
    # pytest's loop can't be reused there ("attached to a different loop").
    # NullPool opens a fresh connection per checkout instead of reusing one.
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_sessionmaker(test_engine):
    return async_sessionmaker(bind=test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(test_sessionmaker):
    async with test_sessionmaker() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _clean_db(test_sessionmaker, request):
    """Runs after every test that pulled in the DB fixtures (autouse, but a
    no-op unless test_sessionmaker was actually resolved this test)."""
    yield
    if "test_sessionmaker" in request.fixturenames:
        async with test_sessionmaker() as session:
            await session.execute(delete(Project))
            await session.commit()
