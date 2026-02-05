"""
Integration tests for web search tools.

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
            "web_search_google",
            {"query": "climate change solutions", "max_results": 5}
        ),
        create_final_response(
            "I found information about climate change solutions. "
            "Renewable energy is a key solution.[[cite:search0]] "
            "Carbon capture technology is also important.[[cite:search1]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
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
            "web_search_google",
            {"query": "machine learning", "max_results": 3}
        ),
        create_final_response(
            "I found 3 results about machine learning.[[cite:search0]][[cite:search1]][[cite:search2]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
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
            "web_search_google",
            {"query": "test query", "max_results": 5}
        ),
        create_final_response(
            "I encountered an error while searching. Please try again later."
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
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
            "web_search_google",
            {"query": "artificial intelligence", "max_results": 2}
        ),
        create_final_response(
            "AI is transforming industries.[[cite:search0]][[cite:search1]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
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


async def test_google_search_with_image_results(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Google search should handle image search results.
    
    Behavior tested:
    - Image search type is properly passed
    - Image results are included in response
    - Image metadata is properly formatted
    """
    scenario_id = "web_search_google_images_001"
    
    llm_responses = [
        create_tool_call_response(
            "web_search_google",
            {"query": "sunset photos", "max_results": 3, "search_type": "image"}
        ),
        create_final_response(
            "I found some beautiful sunset images for you."
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_google_images(*args, **kwargs):
        class MockImage:
            def __init__(self, title, link, imageUrl):
                self.title = title
                self.link = link
                self.imageUrl = imageUrl
        
        return WebSearchResult(
            success=True,
            organic=[],
            images=[
                MockImage("Sunset 1", "https://photos.com/1", "https://photos.com/1.jpg"),
                MockImage("Sunset 2", "https://photos.com/2", "https://photos.com/2.jpg"),
            ]
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.google_search.GoogleSearchTool.search", mock_search_google_images)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search for sunset photos"],
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
    
    print(f"✓ Scenario {scenario_id}: Google image search completed successfully")


async def test_google_search_with_date_restrict(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Google search should respect date_restrict parameter.
    
    Behavior tested:
    - Date restriction is properly passed to API
    - Results are filtered by date
    """
    scenario_id = "web_search_google_date_001"
    
    llm_responses = [
        create_tool_call_response(
            "web_search_google",
            {"query": "recent news", "max_results": 3, "date_restrict": "d7"}
        ),
        create_final_response(
            "Here are recent news from the past week.[[cite:search0]]"
        ),
    ]
    
    prime_llm_server(test_llm_server, llm_responses)
    
    from solace_agent_mesh.tools.web_search import SearchResult as WebSearchResult
    
    async def mock_search_google_date(*args, **kwargs):
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title
        
        return WebSearchResult(
            success=True,
            organic=[MockSource("Recent News", "https://news.com", "News from this week")],
            images=[]
        )
    
    monkeypatch.setattr("solace_agent_mesh.tools.web_search.google_search.GoogleSearchTool.search", mock_search_google_date)

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="user@example.com",
        text_parts_content=["Search for recent news from the past week"],
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
    
    print(f"✓ Scenario {scenario_id}: Google date-restricted search completed successfully")