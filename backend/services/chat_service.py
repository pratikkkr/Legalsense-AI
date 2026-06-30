"""
Chat service — manages conversations, messages, and RAG interaction.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.chains.llm import LLMMessage
from backend.chains.rag import RAGChain, extract_citations
from backend.core.logging_config import get_logger
from backend.core.models import Conversation, Message, MessageRole
from backend.schemas.chat import ConversationDetail, ConversationSummary, MessageResponse

log = get_logger(__name__)


class ChatService:
    """Handles conversation CRUD and RAG-powered chat."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.rag = RAGChain()

    async def list_conversations(
        self, user_id: uuid.UUID
    ) -> list[ConversationSummary]:
        """List the user's conversations, newest first."""
        result = await self.db.execute(
            select(
                Conversation,
                func.count(Message.id).label("msg_count"),
            )
            .outerjoin(Message)
            .where(Conversation.user_id == user_id)
            .group_by(Conversation.id)
            .order_by(Conversation.updated_at.desc())
        )
        rows = result.all()
        return [
            ConversationSummary(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=msg_count,
            )
            for conv, msg_count in rows
        ]

    async def get_conversation(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> ConversationDetail | None:
        """Fetch a full conversation with messages."""
        result = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .options(selectinload(Conversation.messages))
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return None
        return ConversationDetail(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            messages=[
                MessageResponse(
                    id=m.id,
                    role=m.role.value,
                    content=m.content,
                    citations=m.citations,
                    model_used=m.model_used,
                    created_at=m.created_at,
                )
                for m in conv.messages
            ],
        )

    async def delete_conversation(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """Delete a conversation and all its messages."""
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return False
        await self.db.delete(conv)
        await self.db.flush()
        return True

    async def chat(
        self,
        user_id: uuid.UUID,
        message: str,
        conversation_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Send a message, run RAG, save both messages, return the
        assistant response with citations.
        """
        # Resolve or create conversation.
        if conversation_id:
            result = await self.db.execute(
                select(Conversation)
                .where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                )
                .options(selectinload(Conversation.messages))
            )
            conv = result.scalar_one_or_none()
            if conv is None:
                raise ValueError("Conversation not found")
        else:
            conv = Conversation(user_id=user_id, title="New Conversation")
            self.db.add(conv)
            await self.db.flush()
            await self.db.refresh(conv)

        # Build history from prior messages.
        history: list[LLMMessage] = []
        if conversation_id and conv.messages:
            for m in conv.messages[-10:]:
                history.append(LLMMessage(role=m.role.value, content=m.content))

        # Save user message.
        user_msg = Message(
            conversation_id=conv.id,
            role=MessageRole.USER,
            content=message,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # Run RAG.
        rag_result = await self.rag.query(message, history=history)

        # Save assistant message.
        assistant_msg = Message(
            conversation_id=conv.id,
            role=MessageRole.ASSISTANT,
            content=rag_result["content"],
            citations=rag_result.get("citations"),
            token_count=rag_result.get("usage", {}).get("total_tokens", 0),
            model_used=rag_result.get("model"),
        )
        self.db.add(assistant_msg)

        # Auto-generate title for new conversations.
        if not conversation_id or conv.title == "New Conversation":
            try:
                title = await self.rag.generate_title(message)
                conv.title = title
            except Exception:
                conv.title = message[:60]

        await self.db.flush()

        log.info(
            "chat_completed",
            conversation_id=str(conv.id),
            tokens=rag_result.get("usage", {}).get("total_tokens", 0),
        )

        return {
            "conversation_id": str(conv.id),
            "message": MessageResponse(
                id=assistant_msg.id,
                role="assistant",
                content=rag_result["content"],
                citations=rag_result.get("citations"),
                model_used=rag_result.get("model"),
                created_at=assistant_msg.created_at,
            ),
        }
