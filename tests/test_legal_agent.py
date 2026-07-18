"""
Tests for LegalAgent's tool-calling loop (backend/agents/legal_agent.py):
tool dispatch, the MAX_ITERATIONS cutoff, and regression coverage for the
untrusted-tool-result delimiter wrapping added during the security audit.
"""

import pytest

from backend.agents.legal_agent import LegalAgent
from backend.chains.llm import LLMResponse, LLMToolResponse, ToolCall


@pytest.mark.asyncio
async def test_run_returns_immediately_when_no_tools_requested(
    mock_llm_provider, mock_qdrant
):
    mock_llm_provider.generate_with_tools.return_value = LLMToolResponse(
        content="Direct answer, no tools needed.", tool_calls=[], model="mock-model"
    )

    agent = LegalAgent()
    result = await agent.run("What is Section 1 about?")

    assert result["content"] == "Direct answer, no tools needed."
    assert result["tool_calls_made"] == []
    mock_llm_provider.generate_with_tools.assert_awaited_once()
    mock_llm_provider.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_executes_tool_then_returns_final_answer(
    mock_llm_provider, mock_qdrant
):
    mock_llm_provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=[ToolCall(name="search_sections", arguments={"query": "negligence"})],
            model="mock-model",
        ),
        LLMToolResponse(content="Final synthesized answer.", tool_calls=[], model="mock-model"),
    ]

    agent = LegalAgent()
    result = await agent.run("What does the law say about negligence?")

    assert result["content"] == "Final synthesized answer."
    assert len(result["tool_calls_made"]) == 1
    assert result["tool_calls_made"][0]["name"] == "search_sections"
    assert mock_llm_provider.generate_with_tools.await_count == 2
    mock_llm_provider.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_tool_name_reports_gracefully(mock_llm_provider, mock_qdrant):
    mock_llm_provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=[ToolCall(name="not_a_real_tool", arguments={})],
            model="mock-model",
        ),
        LLMToolResponse(content="Recovered answer.", tool_calls=[], model="mock-model"),
    ]

    agent = LegalAgent()
    result = await agent.run("Trigger an unknown tool")

    assert result["tool_calls_made"][0]["result_preview"] == "Unknown tool: not_a_real_tool"
    assert result["content"] == "Recovered answer."


@pytest.mark.asyncio
async def test_max_iterations_cutoff_falls_back_to_final_summary(
    mock_llm_provider, mock_qdrant
):
    # The LLM always requests another tool call and never stops on its own.
    mock_llm_provider.generate_with_tools.return_value = LLMToolResponse(
        content=None,
        tool_calls=[ToolCall(name="search_sections", arguments={"query": "x"})],
        model="mock-model",
    )
    mock_llm_provider.generate.return_value = LLMResponse(
        content="Fallback summary after hitting the iteration cap.", model="mock-model"
    )

    agent = LegalAgent()
    result = await agent.run("Ask something that keeps triggering tools")

    assert mock_llm_provider.generate_with_tools.await_count == LegalAgent.MAX_ITERATIONS
    mock_llm_provider.generate.assert_awaited_once()
    assert result["content"] == "Fallback summary after hitting the iteration cap."
    assert len(result["tool_calls_made"]) == LegalAgent.MAX_ITERATIONS


@pytest.mark.asyncio
async def test_tool_results_are_wrapped_as_untrusted_data(mock_llm_provider, mock_qdrant):
    """
    Regression test for the prompt-injection hardening added in the
    security audit: tool results fed back to the LLM must be delimited
    and explicitly labeled as untrusted, non-instructional data.
    """
    mock_llm_provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=[ToolCall(name="search_sections", arguments={"query": "negligence"})],
            model="mock-model",
        ),
        LLMToolResponse(content="Done.", tool_calls=[], model="mock-model"),
    ]

    agent = LegalAgent()
    await agent.run("Search for negligence provisions")

    second_call_messages = mock_llm_provider.generate_with_tools.call_args_list[1].args[0]
    tool_result_message = second_call_messages[-1]

    assert tool_result_message.role == "user"
    assert "untrusted retrieved data" in tool_result_message.content
    assert "<<<BEGIN_TOOL_RESULT>>>" in tool_result_message.content
    assert "<<<END_TOOL_RESULT>>>" in tool_result_message.content
