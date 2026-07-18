"""
Provider-agnostic LLM abstraction layer.

Supports Gemini, OpenAI, Anthropic, Ollama, and Azure OpenAI through a
common interface.  The active provider is determined by ``LLM_PROVIDER``
in the application config — switching providers requires only a config
change, never a code change.

Usage::

    from backend.chains.llm import create_llm_provider

    llm = create_llm_provider()
    response = await llm.generate([LLMMessage(role="user", content="Hello")])
    print(response.content)
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from backend.core.config import get_settings
from backend.core.logging_config import get_logger

log = get_logger(__name__)


# ── Data classes ────────────────────────────────────────────────────


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class LLMToolResponse:
    content: str | None
    tool_calls: list[ToolCall]
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)


# ── Abstract provider ──────────────────────────────────────────────


class LLMProvider(ABC):
    """
    Abstract base for all LLM providers.

    Every provider must implement ``generate``, ``stream``, and
    ``generate_with_tools``.  This enables transparent provider
    swapping at the config level.
    """

    def __init__(self, model: str, temperature: float, max_tokens: int):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    async def generate(
        self, messages: list[LLMMessage], **kwargs
    ) -> LLMResponse:
        """Produce a single, complete response."""

    @abstractmethod
    async def stream(
        self, messages: list[LLMMessage], **kwargs
    ) -> AsyncIterator[str]:
        """Yield incremental text chunks as they become available."""

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        **kwargs,
    ) -> LLMToolResponse:
        """Generate a response that may include tool/function calls."""


# ── Gemini ──────────────────────────────────────────────────────────


class GeminiProvider(LLMProvider):
    """Google Gemini via the ``google-generativeai`` SDK."""

    def __init__(self, model: str, temperature: float, max_tokens: int, api_key: str):
        super().__init__(model, temperature, max_tokens)
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._genai = genai
        self._model = genai.GenerativeModel(model)

    def _to_genai_messages(self, messages: list[LLMMessage]) -> tuple[str | None, list[dict]]:
        system = None
        history: list[dict] = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                role = "user" if m.role == "user" else "model"
                history.append({"role": role, "parts": [m.content]})
        return system, history

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        system, history = self._to_genai_messages(messages)
        model = self._model
        if system:
            model = self._genai.GenerativeModel(
                self.model, system_instruction=system
            )
        config = self._genai.GenerationConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
        response = await asyncio.to_thread(
            lambda: model.generate_content(history, generation_config=config)
        )
        try:
            content = response.text
        except ValueError:
            content = "Response blocked by safety filters."
        return LLMResponse(
            content=content,
            model=self.model,
            usage=LLMUsage(
                prompt_tokens=getattr(response.usage_metadata, "prompt_token_count", 0),
                completion_tokens=getattr(response.usage_metadata, "candidates_token_count", 0),
                total_tokens=getattr(response.usage_metadata, "total_token_count", 0),
            ),
        )

    async def stream(self, messages: list[LLMMessage], **kwargs) -> AsyncIterator[str]:
        system, history = self._to_genai_messages(messages)
        model = self._model
        if system:
            model = self._genai.GenerativeModel(
                self.model, system_instruction=system
            )
        config = self._genai.GenerationConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )

        def _stream():
            return model.generate_content(
                history, generation_config=config, stream=True
            )

        response = await asyncio.to_thread(_stream)
        for chunk in response:
            try:
                if chunk.text:
                    yield chunk.text
            except ValueError:
                pass

    async def generate_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolDefinition], **kwargs
    ) -> LLMToolResponse:
        system, history = self._to_genai_messages(messages)
        genai_tools = []
        for t in tools:
            genai_tools.append(
                self._genai.protos.Tool(
                    function_declarations=[
                        self._genai.protos.FunctionDeclaration(
                            name=t.name,
                            description=t.description,
                            parameters=t.parameters,
                        )
                    ]
                )
            )
        model = self._genai.GenerativeModel(
            self.model,
            system_instruction=system,
            tools=genai_tools,
        )
        config = self._genai.GenerationConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
        response = await asyncio.to_thread(
            lambda: model.generate_content(history, generation_config=config)
        )
        tool_calls = []
        content = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                tool_calls.append(
                    ToolCall(name=fc.name, arguments=dict(fc.args))
                )
            elif part.text:
                content = part.text
        return LLMToolResponse(
            content=content,
            tool_calls=tool_calls,
            model=self.model,
        )


# ── OpenAI ──────────────────────────────────────────────────────────


class OpenAIProvider(LLMProvider):
    """OpenAI / Azure OpenAI via the ``openai`` SDK."""

    def __init__(
        self,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: str,
        base_url: str | None = None,
    ):
        super().__init__(model, temperature, max_tokens)
        from openai import AsyncOpenAI

        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)

    def _to_openai_messages(self, messages: list[LLMMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=self._to_openai_messages(messages),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=self.model,
            usage=LLMUsage(
                prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
                total_tokens=resp.usage.total_tokens if resp.usage else 0,
            ),
        )

    async def stream(self, messages: list[LLMMessage], **kwargs) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=self._to_openai_messages(messages),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def generate_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolDefinition], **kwargs
    ) -> LLMToolResponse:
        import json

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=self._to_openai_messages(messages),
            tools=openai_tools,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        choice = resp.choices[0]
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )
        return LLMToolResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            model=self.model,
            usage=LLMUsage(
                prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
                total_tokens=resp.usage.total_tokens if resp.usage else 0,
            ),
        )


# ── Anthropic ───────────────────────────────────────────────────────


class AnthropicProvider(LLMProvider):
    """Anthropic Claude via the ``anthropic`` SDK."""

    def __init__(self, model: str, temperature: float, max_tokens: int, api_key: str):
        super().__init__(model, temperature, max_tokens)
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)

    def _split_system(self, messages: list[LLMMessage]) -> tuple[str, list[dict]]:
        system = ""
        msgs = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                msgs.append({"role": m.role, "content": m.content})
        return system, msgs

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        system, msgs = self._split_system(messages)
        resp = await self._client.messages.create(
            model=self.model,
            system=system,
            messages=msgs,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = "".join(
            block.text for block in resp.content if hasattr(block, "text")
        )
        return LLMResponse(
            content=content,
            model=self.model,
            usage=LLMUsage(
                prompt_tokens=resp.usage.input_tokens,
                completion_tokens=resp.usage.output_tokens,
                total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
            ),
        )

    async def stream(self, messages: list[LLMMessage], **kwargs) -> AsyncIterator[str]:
        system, msgs = self._split_system(messages)
        async with self._client.messages.stream(
            model=self.model,
            system=system,
            messages=msgs,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def generate_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolDefinition], **kwargs
    ) -> LLMToolResponse:

        system, msgs = self._split_system(messages)
        anthropic_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]
        resp = await self._client.messages.create(
            model=self.model,
            system=system,
            messages=msgs,
            tools=anthropic_tools,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        tool_calls = []
        content = None
        for block in resp.content:
            if block.type == "tool_use":
                tool_calls.append(
                    ToolCall(name=block.name, arguments=block.input)
                )
            elif block.type == "text":
                content = block.text
        return LLMToolResponse(
            content=content,
            tool_calls=tool_calls,
            model=self.model,
            usage=LLMUsage(
                prompt_tokens=resp.usage.input_tokens,
                completion_tokens=resp.usage.output_tokens,
                total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
            ),
        )


# ── Ollama ──────────────────────────────────────────────────────────


class OllamaProvider(LLMProvider):
    """Local Ollama via its OpenAI-compatible endpoint."""

    def __init__(self, model: str, temperature: float, max_tokens: int, base_url: str):
        super().__init__(model, temperature, max_tokens)
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key="ollama", base_url=f"{base_url}/v1")

    def _to_messages(self, messages: list[LLMMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=self._to_messages(messages),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return LLMResponse(
            content=resp.choices[0].message.content or "",
            model=self.model,
        )

    async def stream(self, messages: list[LLMMessage], **kwargs) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=self._to_messages(messages),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def generate_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolDefinition], **kwargs
    ) -> LLMToolResponse:
        # Ollama's tool support is model-dependent; fall back to text.
        resp = await self.generate(messages, **kwargs)
        return LLMToolResponse(
            content=resp.content,
            tool_calls=[],
            model=self.model,
            usage=resp.usage,
        )


# ── Factory ─────────────────────────────────────────────────────────

_provider_instance: LLMProvider | None = None


def create_llm_provider() -> LLMProvider:
    """
    Instantiate the configured LLM provider (singleton).

    The provider type is determined by ``LLM_PROVIDER`` in config.
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    settings = get_settings()
    provider = settings.LLM_PROVIDER
    model = settings.LLM_MODEL
    temp = settings.LLM_TEMPERATURE
    max_tok = settings.LLM_MAX_TOKENS

    log.info("llm_provider_init", provider=provider, model=model)

    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        _provider_instance = GeminiProvider(model, temp, max_tok, settings.GEMINI_API_KEY)

    elif provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        _provider_instance = OpenAIProvider(model, temp, max_tok, settings.OPENAI_API_KEY)

    elif provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        _provider_instance = AnthropicProvider(model, temp, max_tok, settings.ANTHROPIC_API_KEY)

    elif provider == "azure_openai":
        if not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_ENDPOINT:
            raise RuntimeError(
                "AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT are required"
            )
        _provider_instance = OpenAIProvider(
            model,
            temp,
            max_tok,
            settings.AZURE_OPENAI_API_KEY,
            base_url=f"{settings.AZURE_OPENAI_ENDPOINT}/openai/deployments/{model}",
        )

    elif provider == "ollama":
        _provider_instance = OllamaProvider(
            model, temp, max_tok, settings.OLLAMA_BASE_URL
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

    return _provider_instance
