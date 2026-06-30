"""
End-to-end RAG (Retrieval-Augmented Generation) chain.

Orchestrates: query → retrieve → build context → generate / stream.
Handles conversation memory, context-window optimization, and citation
extraction.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import AsyncIterator

from backend.chains.llm import LLMMessage, LLMResponse, create_llm_provider
from backend.chains.prompts import (
    SYSTEM_PROMPT,
    TITLE_GENERATION_PROMPT,
    build_context_block,
    build_rag_prompt,
)
from backend.chains.retriever import HybridRetriever, RetrievedChunk
from backend.core.config import get_settings
from backend.core.logging_config import get_logger

log = get_logger(__name__)
_settings = get_settings()


# ── Citation extraction ─────────────────────────────────────────────

_CITE_PATTERN = re.compile(
    r"\[Section\s+([\dA-Za-z]+),\s*(.+?)\]", re.IGNORECASE
)


def extract_citations(
    text: str, retrieved: list[RetrievedChunk]
) -> list[dict]:
    """
    Parse ``[Section X, Act Name]`` references from the LLM output and
    match them against the retrieved chunks to produce structured
    citation objects.
    """
    matches = _CITE_PATTERN.findall(text)
    citations: list[dict] = []
    seen: set[str] = set()

    for sec_num, act_hint in matches:
        key = f"{sec_num}:{act_hint.strip().lower()}"
        if key in seen:
            continue
        seen.add(key)

        # Try to match against a retrieved chunk.
        best: RetrievedChunk | None = None
        for chunk in retrieved:
            if chunk.section_number == sec_num:
                if act_hint.strip().lower() in chunk.act_title.lower():
                    best = chunk
                    break
                if best is None:
                    best = chunk

        if best:
            citations.append(
                {
                    "act_title": best.act_title,
                    "section_number": best.section_number,
                    "section_title": best.section_title,
                    "text_snippet": best.text[:300],
                }
            )
        else:
            citations.append(
                {
                    "act_title": act_hint.strip(),
                    "section_number": sec_num,
                    "section_title": "",
                    "text_snippet": "",
                }
            )
    return citations


# ── Context optimisation ────────────────────────────────────────────


def _truncate_context(chunks: list[RetrievedChunk], max_tokens: int) -> list[RetrievedChunk]:
    """Keep only enough chunks to fit within the token budget (heuristic: 1 token ≈ 4 chars)."""
    budget = max_tokens * 4
    selected: list[RetrievedChunk] = []
    used = 0
    for chunk in chunks:
        cost = len(chunk.text)
        if used + cost > budget:
            break
        selected.append(chunk)
        used += cost
    return selected


# ── RAG Chain ───────────────────────────────────────────────────────


class RAGChain:
    """
    High-level RAG orchestrator.

    Typical usage::

        chain = RAGChain()
        result = await chain.query("What are the penalties under the IT Act?")
        print(result.content)
        print(result.citations)
    """

    def __init__(
        self,
        top_k: int | None = None,
        max_context_tokens: int | None = None,
    ):
        self.retriever = HybridRetriever(top_k=top_k)
        self.max_context_tokens = max_context_tokens or _settings.RAG_MAX_CONTEXT_TOKENS
        self.llm = create_llm_provider()

    def _build_messages(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        history: list[LLMMessage] | None = None,
    ) -> list[LLMMessage]:
        """Assemble the full message list for the LLM."""
        context_dicts = [
            {
                "act_title": c.act_title,
                "section_number": c.section_number,
                "section_title": c.section_title,
                "chapter": c.chapter,
                "text": c.text,
            }
            for c in chunks
        ]
        context_block = build_context_block(context_dicts)
        rag_user_prompt = build_rag_prompt(context_block, question)

        messages: list[LLMMessage] = [LLMMessage(role="system", content=SYSTEM_PROMPT)]

        # Inject recent conversation history for multi-turn context.
        if history:
            # Keep only the last 10 messages to stay within token limits.
            for msg in history[-10:]:
                messages.append(msg)

        messages.append(LLMMessage(role="user", content=rag_user_prompt))
        return messages

    async def query(
        self,
        question: str,
        act_filter: str | None = None,
        history: list[LLMMessage] | None = None,
    ) -> dict:
        """
        Full RAG pipeline: retrieve → augment → generate.

        Returns a dict with ``content``, ``citations``, ``model``,
        ``usage``, and ``sources``.
        """
        result = self.retriever.retrieve(question, act_filter=act_filter)
        chunks = _truncate_context(result.chunks, self.max_context_tokens)
        messages = self._build_messages(question, chunks, history)

        response: LLMResponse = await self.llm.generate(messages)
        citations = extract_citations(response.content, chunks)

        return {
            "content": response.content,
            "citations": citations,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "sources": [
                {
                    "act_title": c.act_title,
                    "section_number": c.section_number,
                    "section_title": c.section_title,
                    "score": c.score,
                }
                for c in chunks
            ],
        }

    async def stream_query(
        self,
        question: str,
        act_filter: str | None = None,
        history: list[LLMMessage] | None = None,
    ) -> AsyncIterator[str]:
        """
        Streaming variant — yields text chunks as they arrive from the
        LLM.  The caller is responsible for collecting the full text to
        extract citations afterward.
        """
        result = self.retriever.retrieve(question, act_filter=act_filter)
        chunks = _truncate_context(result.chunks, self.max_context_tokens)
        messages = self._build_messages(question, chunks, history)

        async for token in self.llm.stream(messages):
            yield token

    async def generate_title(self, first_message: str) -> str:
        """Generate a short conversation title from the first user message."""
        prompt = TITLE_GENERATION_PROMPT.format(message=first_message[:200])
        messages = [LLMMessage(role="user", content=prompt)]
        response = await self.llm.generate(messages)
        return response.content.strip().strip('"').strip("'")[:100]

    def get_retrieved_chunks(
        self, question: str, act_filter: str | None = None
    ) -> list[RetrievedChunk]:
        """Retrieve without generating — useful for the search API."""
        result = self.retriever.retrieve(question, act_filter=act_filter)
        return _truncate_context(result.chunks, self.max_context_tokens)
