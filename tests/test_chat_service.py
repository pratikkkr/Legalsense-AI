import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import User
from backend.services.chat_service import ChatService


@pytest.mark.asyncio
async def test_chat_creates_conversation_and_persists_messages(
    db_session: AsyncSession, test_user: User, mock_llm_provider, mock_qdrant
):
    svc = ChatService(db_session)
    result = await svc.chat(user_id=test_user.id, message="What is negligence?")

    assert result["message"].content == "Mock answer."
    assert result["message"].role == "assistant"

    conv = await svc.get_conversation(
        uuid.UUID(result["conversation_id"]), test_user.id
    )
    assert conv is not None
    assert len(conv.messages) == 2
    assert conv.messages[0].role == "user"
    assert conv.messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_chat_unknown_conversation_raises_value_error(
    db_session: AsyncSession, test_user: User, mock_llm_provider, mock_qdrant
):
    svc = ChatService(db_session)
    with pytest.raises(ValueError):
        await svc.chat(
            user_id=test_user.id,
            message="Hi",
            conversation_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_list_conversations_empty_for_new_user(
    db_session: AsyncSession, test_user: User, mock_llm_provider
):
    # ChatService.__init__ always constructs a RAGChain (and therefore an LLM
    # provider), even though list_conversations() never calls it.
    svc = ChatService(db_session)
    conversations = await svc.list_conversations(test_user.id)
    assert conversations == []


@pytest.mark.asyncio
async def test_delete_conversation_returns_false_when_missing(
    db_session: AsyncSession, test_user: User, mock_llm_provider
):
    svc = ChatService(db_session)
    deleted = await svc.delete_conversation(uuid.uuid4(), test_user.id)
    assert deleted is False


@pytest.mark.asyncio
async def test_title_generation_failure_falls_back_to_truncated_message(
    db_session: AsyncSession, test_user: User, mock_llm_provider, mock_qdrant, monkeypatch
):
    async def _boom(self, first_message):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("backend.chains.rag.RAGChain.generate_title", _boom)

    svc = ChatService(db_session)
    long_message = "x" * 200
    result = await svc.chat(user_id=test_user.id, message=long_message)

    conv = await svc.get_conversation(
        uuid.UUID(result["conversation_id"]), test_user.id
    )
    assert conv.title == long_message[:60]
