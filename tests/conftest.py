import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.chains.llm import LLMResponse, LLMToolResponse
from backend.core.database import Base, get_db
from backend.core.models import User, UserRole
from backend.core.security import hash_password
from backend.main import app

# SQLite in-memory is fast and sufficient for exercising the schema in tests.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    # Override database dependency in FastAPI application
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
        
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    # Seed a standard test user in the session database
    user = User(
        email="testuser@example.com",
        hashed_password=hash_password("password123"),
        full_name="Test User",
        role=UserRole.USER,
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()
    return user

@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    # Get auth headers for test client
    reg_data = {
        "email": "authuser@example.com",
        "password": "securepassword123",
        "full_name": "Auth User"
    }
    await client.post("/api/v1/auth/register", json=reg_data)
    login_res = await client.post("/api/v1/auth/login", json={
        "email": reg_data["email"],
        "password": reg_data["password"]
    })
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_llm_provider(monkeypatch) -> MagicMock:
    """
    Fake LLMProvider whose generate()/generate_with_tools()/stream() are
    scriptable via .generate.return_value / .generate_with_tools.return_value.

    Patches the provider factory everywhere it's imported directly
    (RAGChain and LegalAgent both do `from backend.chains.llm import
    create_llm_provider`, so patching the source alone is not enough).
    """
    provider = MagicMock()
    provider.model = "mock-model"
    provider.generate = AsyncMock(
        return_value=LLMResponse(content="Mock answer.", model="mock-model")
    )
    provider.generate_with_tools = AsyncMock(
        return_value=LLMToolResponse(content="Mock answer.", tool_calls=[], model="mock-model")
    )

    async def _stream(*_args, **_kwargs):
        yield "Mock "
        yield "answer."

    provider.stream = _stream

    monkeypatch.setattr("backend.chains.llm.create_llm_provider", lambda: provider)
    monkeypatch.setattr("backend.chains.rag.create_llm_provider", lambda: provider)
    monkeypatch.setattr("backend.agents.legal_agent.create_llm_provider", lambda: provider)
    return provider


@pytest_asyncio.fixture
async def mock_qdrant(monkeypatch) -> MagicMock:
    """
    Fake Qdrant client + embed_query, patched where `HybridRetriever`
    imports them (`backend.chains.retriever`), returning zero hits by
    default. Override `client.query_points.return_value` per-test for
    specific retrieval results.
    """
    client = MagicMock()
    empty_result = MagicMock()
    empty_result.points = []
    client.query_points.return_value = empty_result

    monkeypatch.setattr("backend.chains.retriever.get_qdrant_client", lambda: client)
    monkeypatch.setattr("backend.chains.retriever.embed_query", lambda query: [0.0] * 768)
    return client
