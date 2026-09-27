# THIS IS A TEST
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base, get_db
from app.main import app

# A separate engine/session for tests, so the app's session isn't reused.
test_engine = create_async_engine(settings.test_database_url, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # Fresh schema per test session.
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    # Override the real DB dependency with the test session.
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """A client that is signed up and logged in as test user."""
    email = "test@example.com"
    password = "testpassword123"

    r = await client.post("/api/signup", json={"email": email, "password": password})
    # If the user already exists from a previous test in the same session, ignore it
    assert r.status_code in (201, 409)

    r = await client.post("/api/login", json={"email": email, "password": password})
    assert r.status_code == 200

    return client
