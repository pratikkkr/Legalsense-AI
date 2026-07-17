import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_creates_new_conversation(
    client: AsyncClient, auth_headers: dict[str, str], mock_llm_provider, mock_qdrant
):
    res = await client.post(
        "/api/v1/chat",
        json={"message": "What is Section 73 of the Contract Act?"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert "conversation_id" in body
    assert body["message"]["role"] == "assistant"
    assert body["message"]["content"] == "Mock answer."
    mock_llm_provider.generate.assert_awaited()


@pytest.mark.asyncio
async def test_chat_continues_existing_conversation(
    client: AsyncClient, auth_headers: dict[str, str], mock_llm_provider, mock_qdrant
):
    first = await client.post(
        "/api/v1/chat", json={"message": "Hello"}, headers=auth_headers
    )
    conversation_id = first.json()["conversation_id"]

    second = await client.post(
        "/api/v1/chat",
        json={"message": "Follow-up question", "conversation_id": conversation_id},
        headers=auth_headers,
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id


@pytest.mark.asyncio
async def test_chat_invalid_conversation_id_returns_404(
    client: AsyncClient, auth_headers: dict[str, str], mock_llm_provider, mock_qdrant
):
    res = await client.post(
        "/api/v1/chat",
        json={
            "message": "Hi",
            "conversation_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=auth_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_chat_requires_auth(client: AsyncClient):
    res = await client.post("/api/v1/chat", json={"message": "Hi"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_conversation_crud_flow(
    client: AsyncClient, auth_headers: dict[str, str], mock_llm_provider, mock_qdrant
):
    created = await client.post(
        "/api/v1/chat", json={"message": "Hello"}, headers=auth_headers
    )
    conversation_id = created.json()["conversation_id"]

    listed = await client.get("/api/v1/chat/conversations", headers=auth_headers)
    assert listed.status_code == 200
    assert any(c["id"] == conversation_id for c in listed.json())

    detail = await client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=auth_headers
    )
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) == 2  # user + assistant

    deleted = await client.delete(
        f"/api/v1/chat/conversations/{conversation_id}", headers=auth_headers
    )
    assert deleted.status_code == 204

    missing = await client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=auth_headers
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_get_conversation_not_owned_returns_404(
    client: AsyncClient, auth_headers: dict[str, str], mock_llm_provider, mock_qdrant
):
    """A user cannot fetch another user's conversation by guessing its ID (IDOR check)."""
    res = await client.get(
        "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert res.status_code == 404
