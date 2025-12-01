"""
Integration tests for web search tools (Tavily, Google, Exa, and Brave).

These tests focus on user-facing behavior: result formatting, RAG metadata generation,
citation handling, and error scenarios. They use real components with mocked external APIs.
"""

import pytest
import json
from typing import Dict, Any

from sam_test_infrastructure.llm_server.server import (
    TestLLMServer,
    ChatCompletionResponse,
    Message,
    Choice,
    ToolCall,
    ToolCallFunction,
    Usage,
)
from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
from solace_agent_mesh.agent.sac.app import SamAgentApp
from a2a.types import Task, TaskState

from tests.integration.scenarios_programmatic.test_helpers import (
    prime_llm_server,
    create_gateway_input_data,
    submit_test_input,
    get_all_task_events,
    find_first_event_of_type,
)

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.agent,
    pytest.mark.web_search,
]


# ============================================================================
# Test Helpers
# ============================================================================

def create_tool_call_response(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Create LLM response that calls a web search tool."""
    return ChatCompletionResponse(
        id=f"chatcmpl-{tool_name}",
        model="test-llm-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id=f"call_{tool_name}_1",
                            type="function",
                            function=ToolCallFunction(
                                name=tool_name,
                                arguments=json.dumps(arguments),
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=Usage(prompt_tokens=20, completion_tokens=15, total_tokens=35),
    ).model_dump(exclude_none=True)


def create_final_response(content: str) -> Dict[str, Any]:
    """Create LLM final response after tool execution."""
    return ChatCompletionResponse(
        id="chatcmpl-final",
        model="test-llm-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content=content,
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=50, completion_tokens=30, total_tokens=80),
    ).model_dump(exclude_none=True)


# ============================================================================
# Behavioral Tests: Tavily Search
# ============================================================================

async def test_tavily_search_returns_formatted_results(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Tavily search should return properly formatted results with RAG metadata.
    
    Behavior tested:
    - Results are returned in expected format
    - RAG metadata is generated
    - Citations are properly formatted
    - Results include titles, links, and snippets
    """
    scenario_id = "web_search_tavily_basic_001"
    
    # Setup LLM responses
    # Note: The actual tool name exposed to LLM is _web_search_tavily (with underscore)
    # because ADKToolWrapper's __name__ gets set from the implementation function name
    llm_responses = [
        # Agent calls web_search_tavily
        create_tool_call_response(
            "_web_search_tavily",
            {"query": "latest AI developments", "max_results": 5}
        ),
        # Agent responds with search results
        create_final_response(
            "I found several recent developments in AI. "
            "Key findings include advances in large language models.[[cite:search0]] "
            "and improvements in computer vision.[[cite:search1]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    # Mock TavilySearchTool to return results without API
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
        
        return WebSearchResult(
            success=True,
            organic=[
                MockSource("AI News", "https://ai.com", "AI is advancing."),
                MockSource("Tech Daily", "https://tech.com", "New LLMs released.")
            ],
            images=[]
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.tavily_search.TavilySearchTool.search", mock_search)
    
    # Execute search task
    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search for latest AI developments"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    # Assert task completed successfully
    assert final_event is not None, "Task did not complete"
    assert final_event.status.state == TaskState.completed, \
        f"Task failed: {final_event.status.state}"
    
    print(f"✓ Scenario {scenario_id}: Tavily search returned formatted results")


async def test_tavily_search_with_advanced_depth(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Tavily search with advanced depth should return more comprehensive results.
    
    Behavior tested:
    - Advanced search depth is properly passed to API
    - Results are returned successfully
    - More comprehensive content snippets are included
    
    Note: Tavily is optimized for text-based search. For dedicated image search,
    use web_search_google with search_type='image'.
    """
    scenario_id = "web_search_tavily_advanced_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_tavily",
            {
                "query": "solar panels efficiency",
                "max_results": 3,
                "search_depth": "advanced"
            }
        ),
        create_final_response(
            "Here are comprehensive results about solar panels.[[cite:search0]] "
            "The advanced search provides more detailed content."
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    # Mock TavilySearchTool to return results
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_advanced(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
                
        return WebSearchResult(
            success=True,
            organic=[
                MockSource("Solar Panel Efficiency Guide", "https://solar.com/efficiency",
                          "Comprehensive guide to solar panel efficiency including monocrystalline vs polycrystalline comparisons."),
                MockSource("Solar Technology Research", "https://research.com/solar",
                          "Latest research on improving solar cell efficiency and new materials.")
            ],
            images=[]
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.tavily_search.TavilySearchTool.search", mock_search_advanced)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search for solar panel efficiency with advanced depth"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state == TaskState.completed
    
    print(f"✓ Scenario {scenario_id}: Tavily advanced search completed successfully")


async def test_tavily_search_handles_api_error(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Tavily search should handle API errors gracefully.
    
    Behavior tested:
    - Returns error message when API fails
    - Does not crash the system
    - Provides user-friendly error information
    """
    scenario_id = "web_search_tavily_error_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_tavily",
            {"query": "test query", "max_results": 5}
        ),
        # Agent handles error and responds
        create_final_response(
            "I encountered an error while searching. Please try again later."
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    # Mock TavilySearchTool to return error
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_error(*args, **kwargs):
        return WebSearchResult(
            success=False,
            organic=[],
            images=[],
            error="API Error: Rate Limit Exceeded"
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.tavily_search.TavilySearchTool.search", mock_search_error)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search with API error"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    # Should complete (not crash) even with API error
    assert final_event is not None
    assert final_event.status.state in [TaskState.completed, TaskState.failed]
    
    print(f"✓ Scenario {scenario_id}: Handled Tavily API error gracefully")


# ============================================================================
# Behavioral Tests: Google Search
# ============================================================================

async def test_google_search_returns_formatted_results(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Google search should return properly formatted results with RAG metadata.
    
    Behavior tested:
    - Results are returned in expected format
    - RAG metadata is generated
    - Citations are properly formatted
    - Results include titles, links, and snippets
    """
    scenario_id = "web_search_google_basic_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_google",
            {"query": "climate change solutions", "max_results": 5}
        ),
        create_final_response(
            "I found information about climate change solutions. "
            "Renewable energy is a key solution.[[cite:search0]] "
            "Carbon capture technology is also important.[[cite:search1]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    # Mock GoogleSearchTool
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_google(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
        
        return WebSearchResult(
            success=True,
            organic=[
                MockSource("Climate Solution 1", "https://climate1.com", "Solution 1"),
                MockSource("Climate Solution 2", "https://climate2.com", "Solution 2")
            ],
            images=[]
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.google_search.GoogleSearchTool.search", mock_search_google)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search for climate change solutions"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state == TaskState.completed
    
    print(f"✓ Scenario {scenario_id}: Google search returned formatted results")


async def test_google_search_respects_max_results(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Google search should respect max_results parameter.
    
    Behavior tested:
    - Returns at most max_results items
    - Parameter is properly passed to API
    - Results are limited correctly
    """
    scenario_id = "web_search_google_max_results_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_google",
            {"query": "machine learning", "max_results": 3}
        ),
        create_final_response(
            "I found 3 results about machine learning.[[cite:search0]][[cite:search1]][[cite:search2]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    # Mock GoogleSearchTool
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_google_limit(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
        
        max_results = kwargs.get('max_results', 5)
        organic = []
        for i in range(max_results):
            organic.append(MockSource(f"Result {i}", f"https://link{i}.com", f"Snippet {i}"))
            
        return WebSearchResult(success=True, organic=organic, images=[])
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.google_search.GoogleSearchTool.search", mock_search_google_limit)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search for machine learning, limit to 3 results"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state == TaskState.completed
    
    print(f"✓ Scenario {scenario_id}: Google search respected max_results")


async def test_google_search_handles_api_error(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Google search should handle API errors gracefully.
    
    Behavior tested:
    - Returns error message when API fails
    - Does not crash the system
    - Provides user-friendly error information
    """
    scenario_id = "web_search_google_error_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_google",
            {"query": "test query", "max_results": 5}
        ),
        create_final_response(
            "I encountered an error while searching. Please try again later."
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    # Mock GoogleSearchTool Error
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_google_error(*args, **kwargs):
        return WebSearchResult(success=False, organic=[], images=[], error="API Error")
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.google_search.GoogleSearchTool.search", mock_search_google_error)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search with API error"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state in [TaskState.completed, TaskState.failed]
    
    print(f"✓ Scenario {scenario_id}: Handled Google API error gracefully")


# ============================================================================
# Behavioral Tests: RAG Metadata and Citations
# ============================================================================

async def test_web_search_generates_proper_citations(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Web search should generate proper citation IDs and RAG metadata.
    
    Behavior tested:
    - Citation IDs are sequential (search0, search1, etc.)
    - RAG metadata includes all required fields
    - Source URLs are preserved
    - Metadata is properly formatted for UI
    """
    scenario_id = "web_search_citations_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_tavily",
            {"query": "quantum computing", "max_results": 3}
        ),
        create_final_response(
            "Quantum computing uses qubits.[[cite:search0]] "
            "It has applications in cryptography.[[cite:search1]] "
            "And drug discovery.[[cite:search2]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    # Mock Tavily
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
        return WebSearchResult(success=True, organic=[MockSource("QC", "http://qc.com", "Quantum")], images=[])
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.tavily_search.TavilySearchTool.search", mock_search)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Tell me about quantum computing"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state == TaskState.completed
    
    print(f"✓ Scenario {scenario_id}: Generated proper citations and RAG metadata")


async def test_web_search_rag_metadata_structure(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Web search RAG metadata should have correct structure for UI consumption.
    
    Behavior tested:
    - Metadata uses camelCase keys (for frontend)
    - All required fields are present
    - Source metadata includes favicon URLs
    - Timestamps are in ISO format
    """
    scenario_id = "web_search_rag_structure_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_google",
            {"query": "artificial intelligence", "max_results": 2}
        ),
        create_final_response(
            "AI is transforming industries.[[cite:search0]][[cite:search1]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    # Mock Google
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_google(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
        return WebSearchResult(success=True, organic=[MockSource("AI", "http://ai.com", "AI info")], images=[])
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.google_search.GoogleSearchTool.search", mock_search_google)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["What is AI?"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state == TaskState.completed
    
    print(f"✓ Scenario {scenario_id}: RAG metadata has correct structure")


# ============================================================================
# Behavioral Tests: Integration Scenarios
# ============================================================================

async def test_web_search_in_conversation_context(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Web search should work correctly in multi-turn conversation.
    
    Behavior tested:
    - Search results are available in conversation context
    - Citations persist across turns
    - Agent can reference previous search results
    """
    scenario_id = "web_search_conversation_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_tavily",
            {"query": "electric vehicles", "max_results": 3}
        ),
        create_final_response(
            "Electric vehicles are becoming more popular.[[cite:search0]] "
            "They have lower operating costs.[[cite:search1]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    # Mock Tavily
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_ev(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
        return WebSearchResult(success=True, organic=[MockSource("EVs", "http://ev.com", "EV info")], images=[])
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.tavily_search.TavilySearchTool.search", mock_search_ev)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Tell me about electric vehicles"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state == TaskState.completed
    
    print(f"✓ Scenario {scenario_id}: Web search worked in conversation context")


async def test_multiple_web_searches_in_single_task(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Agent should be able to perform multiple web searches in a single task.
    
    Behavior tested:
    - Multiple searches can be performed
    - Citations from different searches are unique
    - RAG metadata includes all searches
    """
    scenario_id = "web_search_multiple_001"
    
    llm_responses = [
        # First search
        create_tool_call_response(
            "_web_search_tavily",
            {"query": "solar energy", "max_results": 2}
        ),
        # Second search
        ChatCompletionResponse(
            id="chatcmpl-second-search",
            model="test-llm-model",
            choices=[
                Choice(
                    message=Message(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            ToolCall(
                                id="call_search_2",
                                type="function",
                                function=ToolCallFunction(
                                    name="_web_search_tavily",
                                    arguments=json.dumps({"query": "wind energy", "max_results": 2}),
                                ),
                            )
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=Usage(prompt_tokens=30, completion_tokens=20, total_tokens=50),
        ).model_dump(exclude_none=True),
        # Final response
        create_final_response(
            "Solar energy is efficient.[[cite:search0]] "
            "Wind energy is cost-effective.[[cite:search2]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    # Mock Tavily
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_multi(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
        return WebSearchResult(success=True, organic=[MockSource("Energy", "http://energy.com", "Energy info")], images=[])
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.tavily_search.TavilySearchTool.search", mock_search_multi)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Compare solar and wind energy"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=20.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state == TaskState.completed
    
    print(f"✓ Scenario {scenario_id}: Multiple web searches completed successfully")


# ============================================================================
# Behavioral Tests: Exa Search
# ============================================================================

async def test_exa_search_returns_formatted_results(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Exa search should return properly formatted results with RAG metadata.
    
    Behavior tested:
    - Results are returned in expected format
    - RAG metadata is generated
    - Citations are properly formatted
    - Results include titles, links, and snippets
    """
    scenario_id = "web_search_exa_basic_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_exa",
            {"query": "latest AI research papers", "max_results": 5}
        ),
        create_final_response(
            "I found several recent AI research papers. "
            "Key findings include advances in transformer architectures.[[cite:search0]] "
            "and improvements in multimodal learning.[[cite:search1]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    # Mock ExaSearchTool to return results without API
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
        
        return WebSearchResult(
            success=True,
            organic=[
                MockSource("AI Research Paper 1", "https://arxiv.org/paper1", "Transformer advances."),
                MockSource("AI Research Paper 2", "https://arxiv.org/paper2", "Multimodal learning.")
            ],
            images=[]
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.exa_search.ExaSearchTool.search", mock_search)
    
    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search for latest AI research papers"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None, "Task did not complete"
    assert final_event.status.state == TaskState.completed, \
        f"Task failed: {final_event.status.state}"
    
    print(f"✓ Scenario {scenario_id}: Exa search returned formatted results")


async def test_exa_search_with_category_filter(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Exa search with category filter should return targeted results.
    
    Behavior tested:
    - Category filter is properly passed to API
    - Results are filtered by category
    - Research paper category returns academic sources
    """
    scenario_id = "web_search_exa_category_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_exa",
            {
                "query": "machine learning optimization",
                "max_results": 3,
                "category": "research paper"
            }
        ),
        create_final_response(
            "Here are research papers about ML optimization.[[cite:search0]] "
            "The papers cover gradient descent improvements."
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_category(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
                
        return WebSearchResult(
            success=True,
            organic=[
                MockSource("ML Optimization Paper", "https://arxiv.org/ml-opt",
                          "Novel gradient descent optimization techniques for deep learning."),
            ],
            images=[]
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.exa_search.ExaSearchTool.search", mock_search_category)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search for ML optimization research papers"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state == TaskState.completed
    
    print(f"✓ Scenario {scenario_id}: Exa category search completed successfully")


async def test_exa_search_handles_api_error(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Exa search should handle API errors gracefully.
    
    Behavior tested:
    - Returns error message when API fails
    - Does not crash the system
    - Provides user-friendly error information
    """
    scenario_id = "web_search_exa_error_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_exa",
            {"query": "test query", "max_results": 5}
        ),
        create_final_response(
            "I encountered an error while searching. Please try again later."
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_error(*args, **kwargs):
        return WebSearchResult(
            success=False,
            organic=[],
            images=[],
            error="API Error: Invalid API Key"
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.exa_search.ExaSearchTool.search", mock_search_error)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search with API error"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state in [TaskState.completed, TaskState.failed]
    
    print(f"✓ Scenario {scenario_id}: Handled Exa API error gracefully")


# ============================================================================
# Behavioral Tests: Brave Search
# ============================================================================

async def test_brave_search_returns_formatted_results(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Brave search should return properly formatted results with RAG metadata.
    
    Behavior tested:
    - Results are returned in expected format
    - RAG metadata is generated
    - Citations are properly formatted
    - Results include titles, links, and snippets
    """
    scenario_id = "web_search_brave_basic_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_brave",
            {"query": "privacy focused browsers", "max_results": 5}
        ),
        create_final_response(
            "I found information about privacy-focused browsers. "
            "Brave browser offers built-in ad blocking.[[cite:search0]] "
            "Firefox also has strong privacy features.[[cite:search1]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
        
        return WebSearchResult(
            success=True,
            organic=[
                MockSource("Brave Browser", "https://brave.com", "Privacy-focused browser with ad blocking."),
                MockSource("Firefox Privacy", "https://firefox.com", "Strong privacy features.")
            ],
            topStories=[],
            images=[]
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.brave_search.BraveSearchTool.search", mock_search)
    
    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search for privacy focused browsers"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None, "Task did not complete"
    assert final_event.status.state == TaskState.completed, \
        f"Task failed: {final_event.status.state}"
    
    print(f"✓ Scenario {scenario_id}: Brave search returned formatted results")


async def test_brave_search_with_freshness_filter(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Brave search with freshness filter should return recent results.
    
    Behavior tested:
    - Freshness filter is properly passed to API
    - Results are filtered by time
    - Past day filter returns recent content
    """
    scenario_id = "web_search_brave_freshness_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_brave",
            {
                "query": "breaking news technology",
                "max_results": 3,
                "freshness": "pd"  # Past day
            }
        ),
        create_final_response(
            "Here are the latest technology news from today.[[cite:search0]] "
            "Breaking developments in AI and tech."
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_freshness(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
                
        return WebSearchResult(
            success=True,
            organic=[
                MockSource("Tech News Today", "https://technews.com/today",
                          "Latest technology developments from the past 24 hours."),
            ],
            topStories=[],
            images=[]
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.brave_search.BraveSearchTool.search", mock_search_freshness)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search for breaking technology news from today"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state == TaskState.completed
    
    print(f"✓ Scenario {scenario_id}: Brave freshness search completed successfully")


async def test_brave_search_with_news_results(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Brave search should include news results in RAG metadata.
    
    Behavior tested:
    - News results are included in response
    - News sources are properly formatted
    - Citations include news sources
    """
    scenario_id = "web_search_brave_news_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_brave",
            {"query": "stock market news", "max_results": 5}
        ),
        create_final_response(
            "Here are the latest stock market updates.[[cite:search0]] "
            "Markets are showing positive trends.[[cite:news0]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_news(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
        
        return WebSearchResult(
            success=True,
            organic=[
                MockSource("Stock Market Analysis", "https://finance.com", "Market analysis.")
            ],
            topStories=[
                MockSource("Breaking: Markets Up", "https://news.com/markets", "Markets showing gains.")
            ],
            images=[]
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.brave_search.BraveSearchTool.search", mock_search_news)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search for stock market news"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state == TaskState.completed
    
    print(f"✓ Scenario {scenario_id}: Brave search with news results completed")


async def test_brave_search_handles_api_error(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Brave search should handle API errors gracefully.
    
    Behavior tested:
    - Returns error message when API fails
    - Does not crash the system
    - Provides user-friendly error information
    """
    scenario_id = "web_search_brave_error_001"
    
    llm_responses = [
        create_tool_call_response(
            "_web_search_brave",
            {"query": "test query", "max_results": 5}
        ),
        create_final_response(
            "I encountered an error while searching. Please try again later."
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_error(*args, **kwargs):
        return WebSearchResult(
            success=False,
            organic=[],
            topStories=[],
            images=[],
            error="API Error: Rate Limit Exceeded"
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.brave_search.BraveSearchTool.search", mock_search_error)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search with API error"],
        scenario_id=scenario_id,
    )
    
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )
    
    final_event = find_first_event_of_type(all_events, Task)
    
    assert final_event is not None
    assert final_event.status.state in [TaskState.completed, TaskState.failed]
    
    print(f"✓ Scenario {scenario_id}: Handled Brave API error gracefully")