"""
Tests for the provider-agnostic LLM layer (backend/chains/llm.py):
the create_llm_provider() factory's provider-selection/error paths,
and GeminiProvider's message conversion, generate(), and
generate_with_tools() behavior — all with the underlying SDKs mocked
so no real network calls are made.
"""

from types import SimpleNamespace

import pytest

import backend.chains.llm as llm_module
from backend.chains.llm import (
    AnthropicProvider,
    GeminiProvider,
    LLMMessage,
    OllamaProvider,
    OpenAIProvider,
    create_llm_provider,
)


def _fake_settings(**overrides) -> SimpleNamespace:
    base = dict(
        LLM_PROVIDER="gemini",
        LLM_MODEL="gemini-2.0-flash",
        LLM_TEMPERATURE=0.2,
        LLM_MAX_TOKENS=4096,
        GEMINI_API_KEY=None,
        OPENAI_API_KEY=None,
        ANTHROPIC_API_KEY=None,
        AZURE_OPENAI_API_KEY=None,
        AZURE_OPENAI_ENDPOINT=None,
        OLLAMA_BASE_URL="http://localhost:11434",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _reset_provider_singleton(monkeypatch):
    """create_llm_provider() caches its result in a module-level singleton."""
    monkeypatch.setattr(llm_module, "_provider_instance", None)


class TestCreateLlmProviderFactory:
    def test_gemini_missing_key_raises(self, monkeypatch):
        monkeypatch.setattr(
            llm_module, "get_settings", lambda: _fake_settings(LLM_PROVIDER="gemini")
        )
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            create_llm_provider()

    def test_openai_missing_key_raises(self, monkeypatch):
        monkeypatch.setattr(
            llm_module, "get_settings", lambda: _fake_settings(LLM_PROVIDER="openai")
        )
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            create_llm_provider()

    def test_anthropic_missing_key_raises(self, monkeypatch):
        monkeypatch.setattr(
            llm_module, "get_settings", lambda: _fake_settings(LLM_PROVIDER="anthropic")
        )
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            create_llm_provider()

    def test_azure_missing_key_raises(self, monkeypatch):
        monkeypatch.setattr(
            llm_module, "get_settings", lambda: _fake_settings(LLM_PROVIDER="azure_openai")
        )
        with pytest.raises(RuntimeError, match="AZURE_OPENAI"):
            create_llm_provider()

    def test_unknown_provider_raises_value_error(self, monkeypatch):
        monkeypatch.setattr(
            llm_module, "get_settings", lambda: _fake_settings(LLM_PROVIDER="not-a-provider")
        )
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_llm_provider()

    def test_gemini_selected_with_key(self, monkeypatch):
        monkeypatch.setattr(
            llm_module,
            "get_settings",
            lambda: _fake_settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="fake-key"),
        )
        monkeypatch.setattr("google.generativeai.configure", lambda **_: None)
        monkeypatch.setattr("google.generativeai.GenerativeModel", lambda *a, **kw: object())
        provider = create_llm_provider()
        assert isinstance(provider, GeminiProvider)

    def test_openai_selected_with_key(self, monkeypatch):
        monkeypatch.setattr(
            llm_module,
            "get_settings",
            lambda: _fake_settings(LLM_PROVIDER="openai", OPENAI_API_KEY="fake-key"),
        )
        provider = create_llm_provider()
        assert isinstance(provider, OpenAIProvider)

    def test_anthropic_selected_with_key(self, monkeypatch):
        monkeypatch.setattr(
            llm_module,
            "get_settings",
            lambda: _fake_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="fake-key"),
        )
        provider = create_llm_provider()
        assert isinstance(provider, AnthropicProvider)

    def test_ollama_selected_needs_no_key(self, monkeypatch):
        monkeypatch.setattr(
            llm_module, "get_settings", lambda: _fake_settings(LLM_PROVIDER="ollama")
        )
        provider = create_llm_provider()
        assert isinstance(provider, OllamaProvider)

    def test_factory_result_is_cached_singleton(self, monkeypatch):
        monkeypatch.setattr(
            llm_module, "get_settings", lambda: _fake_settings(LLM_PROVIDER="ollama")
        )
        first = create_llm_provider()
        second = create_llm_provider()
        assert first is second


class TestGeminiProviderMessages:
    def _make_provider(self, monkeypatch) -> GeminiProvider:
        monkeypatch.setattr("google.generativeai.configure", lambda **_: None)
        monkeypatch.setattr("google.generativeai.GenerativeModel", lambda *a, **kw: object())
        return GeminiProvider(
            model="gemini-2.0-flash", temperature=0.2, max_tokens=4096, api_key="fake-key"
        )

    def test_system_message_extracted_and_history_role_mapped(self, monkeypatch):
        provider = self._make_provider(monkeypatch)
        messages = [
            LLMMessage(role="system", content="You are a legal assistant."),
            LLMMessage(role="user", content="Hello"),
            LLMMessage(role="assistant", content="Hi there"),
        ]
        system, history = provider._to_genai_messages(messages)

        assert system == "You are a legal assistant."
        assert history == [
            {"role": "user", "parts": ["Hello"]},
            {"role": "model", "parts": ["Hi there"]},  # "assistant" maps to Gemini's "model"
        ]

    def test_no_system_message_returns_none(self, monkeypatch):
        provider = self._make_provider(monkeypatch)
        system, history = provider._to_genai_messages(
            [LLMMessage(role="user", content="Hi")]
        )
        assert system is None
        assert history == [{"role": "user", "parts": ["Hi"]}]


class TestGeminiProviderGenerate:
    def _make_provider(self, monkeypatch, fake_model) -> GeminiProvider:
        monkeypatch.setattr("google.generativeai.configure", lambda **_: None)
        monkeypatch.setattr(
            "google.generativeai.GenerativeModel", lambda *a, **kw: fake_model
        )
        return GeminiProvider(
            model="gemini-2.0-flash", temperature=0.2, max_tokens=4096, api_key="fake-key"
        )

    @pytest.mark.asyncio
    async def test_generate_returns_text_and_usage(self, monkeypatch):
        fake_usage = SimpleNamespace(
            prompt_token_count=12, candidates_token_count=8, total_token_count=20
        )
        fake_response = SimpleNamespace(
            text="Section 73 covers damages.", usage_metadata=fake_usage
        )
        fake_model = SimpleNamespace(generate_content=lambda *a, **kw: fake_response)

        provider = self._make_provider(monkeypatch, fake_model)
        result = await provider.generate([LLMMessage(role="user", content="Explain Section 73")])

        assert result.content == "Section 73 covers damages."
        assert result.usage.prompt_tokens == 12
        assert result.usage.completion_tokens == 8
        assert result.usage.total_tokens == 20

    @pytest.mark.asyncio
    async def test_generate_handles_safety_block(self, monkeypatch):
        """response.text raises ValueError when Gemini blocks output on safety grounds."""

        class BlockedResponse:
            usage_metadata = SimpleNamespace(
                prompt_token_count=5, candidates_token_count=0, total_token_count=5
            )

            @property
            def text(self):
                raise ValueError("blocked by safety filters")

        fake_model = SimpleNamespace(generate_content=lambda *a, **kw: BlockedResponse())
        provider = self._make_provider(monkeypatch, fake_model)
        result = await provider.generate([LLMMessage(role="user", content="Hi")])

        assert result.content == "Response blocked by safety filters."

    @pytest.mark.asyncio
    async def test_generate_with_tools_parses_function_call(self, monkeypatch):
        fake_function_call = SimpleNamespace(name="search_sections", args={"query": "negligence"})
        fake_part = SimpleNamespace(function_call=fake_function_call, text=None)
        fake_response = SimpleNamespace(
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=[fake_part]))]
        )
        fake_model = SimpleNamespace(generate_content=lambda *a, **kw: fake_response)

        provider = self._make_provider(monkeypatch, fake_model)
        result = await provider.generate_with_tools(
            [LLMMessage(role="user", content="Find sections about negligence")], tools=[]
        )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "search_sections"
        assert result.tool_calls[0].arguments == {"query": "negligence"}
        assert result.content is None

    @pytest.mark.asyncio
    async def test_generate_with_tools_parses_text_only_response(self, monkeypatch):
        fake_part = SimpleNamespace(function_call=None, text="Final answer text.")
        fake_response = SimpleNamespace(
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=[fake_part]))]
        )
        fake_model = SimpleNamespace(generate_content=lambda *a, **kw: fake_response)

        provider = self._make_provider(monkeypatch, fake_model)
        result = await provider.generate_with_tools(
            [LLMMessage(role="user", content="Summarize")], tools=[]
        )

        assert result.tool_calls == []
        assert result.content == "Final answer text."
