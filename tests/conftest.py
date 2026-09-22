import asyncio
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Ensure test environment
os.environ["ENVIRONMENT"] = "testing"
os.environ["JWT_SECRET"] = "test_super_secret_key_minimum_32_characters_long_12345"

from app.database import Base, get_db
from app.main import app

# Test database: in-memory SQLite with aiosqlite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client):
    """Registers and logs in a test user, returning Bearer auth header and user info."""
    username = "alice_test"
    password = "Password123"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    if reg_resp.status_code == 201:
        data = reg_resp.json()
        return {
            "headers": {"Authorization": f"Bearer {data['access_token']}"},
            "user": data["user"],
            "token": data["access_token"],
        }

    # If already exists in DB session, login
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    data = login_resp.json()
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
        "token": data["access_token"],
    }
