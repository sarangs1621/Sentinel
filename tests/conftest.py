import os
from collections.abc import AsyncGenerator
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


# Must run before `app.*` is imported anywhere, since `app.core.config.settings`
# and `app.db.session.engine` are constructed at import time.
_load_dotenv(Path(__file__).resolve().parent.parent / ".env")
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel_test"
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ["ENVIRONMENT"] = "testing"
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import fakeredis  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

import app.core.redis as app_redis  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def fake_redis(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None, None]:
    """Replace the app's Redis client with an isolated in-memory fakeredis server
    for each test, so cache/counter/rate-limit logic runs against real Redis
    semantics without requiring a live Redis instance."""
    server = fakeredis.FakeServer()

    def _create_fake_client() -> fakeredis.aioredis.FakeRedis:
        return fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)

    monkeypatch.setattr(app_redis, "redis_client", _create_fake_client())
    monkeypatch.setattr(app_redis, "create_redis_client", _create_fake_client)
    monkeypatch.setattr("app.workers.db.create_redis_client", _create_fake_client)
    yield


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    test_engine = create_async_engine(settings.DATABASE_URL, future=True)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """A session bound to a SAVEPOINT that is rolled back after each test,
    so service-layer `commit()` calls don't leak data between tests."""
    async with engine.connect() as connection:
        await connection.begin()
        await connection.begin_nested()

        session_factory = async_sessionmaker(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        session = session_factory()

        yield session

        await session.close()
        await connection.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


DEFAULT_PASSWORD = "Password123!"


async def register_user(
    client: AsyncClient, email: str, password: str = DEFAULT_PASSWORD, full_name: str = "Test User"
) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def login_user(client: AsyncClient, email: str, password: str = DEFAULT_PASSWORD) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def auth_headers(client: AsyncClient, email: str, password: str = DEFAULT_PASSWORD) -> dict[str, str]:
    await register_user(client, email, password)
    tokens = await login_user(client, email, password)
    return {"Authorization": f"Bearer {tokens['access_token']}"}
