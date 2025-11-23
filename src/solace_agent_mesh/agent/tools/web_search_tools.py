"""
Web Search Tools for Solace Agent Mesh
Provides web search capabilities using Tavily and Google Custom Search APIs
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from google.adk.tools import ToolContext

from ...tools.web_search import TavilySearchTool, GoogleSearchTool, SearchResult
from .tool_definition import BuiltinTool
from .registry import tool_registry
from ...gateway.http_sse.routers.dto.rag_dto import create_rag_source, create_rag_search_result

log = logging.getLogger(__name__)

# Category information
CATEGORY_NAME = "web_search"
CATEGORY_DESCRIPTION = "Tools for searching the web and retrieving current information"


async def _web_search_tavily(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_images: bool = False,
    include_answer: bool = False,
    topic: Optional[str] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> str:
    """
    Search the web using Tavily API for current information.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (1-10)
        search_depth: Search depth - 'basic' for quick results, 'advanced' for comprehensive
        include_images: Whether to include image results
        include_answer: Whether to include a direct answer
        topic: Search topic - 'general', 'news', or 'finance'
        tool_context: ADK tool context
        tool_config: Tool configuration containing API keys
        
    Returns:
        JSON string containing search results with sources for citation
    """
    log_identifier = "[web_search_tavily]"
    
    try:
        # Get API key from tool_config
        config = tool_config or {}
        api_key = config.get("tavily_api_key")
        
        if not api_key:
            error_msg = "tavily_api_key not configured in tool_config"
            log.error("%s %s", log_identifier, error_msg)
            return f"Error: {error_msg}"
        
        tool = TavilySearchTool(api_key=api_key)
        
        result: SearchResult = await tool.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,  # type: ignore
            include_images=include_images,
            include_answer=include_answer,
            topic=topic,  # type: ignore
            **kwargs
        )
        
        if not result.success:
            log.error("%s Search failed: %s", log_identifier, result.error)
            return f"Error: {result.error}"
        
        log.info(
            "%s Search successful: %d organic results, %d news, %d images",
            log_identifier,
            len(result.organic),
            len(result.topStories),
            len(result.images)
        )
        
        # Format results as RAG-compatible metadata using DTOs for camelCase conversion
        rag_sources = []
        for i, source in enumerate(result.organic):
            rag_source = create_rag_source(
                citation_id=f"search{i}",
                file_id=f"web_search_{i}",
                filename=source.attribution or source.title,
                title=source.title,
                source_url=source.link,
                url=source.link,
                content_preview=source.snippet,
                relevance_score=1.0,
                source_type="web",
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                metadata={
                    "title": source.title,
                    "link": source.link,
                    "type": "web_search",
                    "favicon": f"https://www.google.com/s2/favicons?domain={source.link}&sz=32" if source.link else ""
                }
            )
            rag_sources.append(rag_source)
        
        # Return both JSON result and RAG metadata (with camelCase keys)
        rag_metadata = create_rag_search_result(
            query=query,
            search_type="web_search",
            timestamp=datetime.now(timezone.utc).isoformat(),
            sources=rag_sources
        )
        
        return {
            "result": result.model_dump_json(),
            "rag_metadata": rag_metadata
        }
        
    except Exception as e:
        log.exception("%s Unexpected error in web search: %s", log_identifier, e)
        return f"Error executing web search: {str(e)}"


async def _web_search_google(
    query: str,
    max_results: int = 5,
    search_type: Optional[str] = None,
    date_restrict: Optional[str] = None,
    safe_search: Optional[str] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> str:
    """
    Search the web using Google Custom Search API.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (1-10)
        search_type: Set to 'image' for image search
        date_restrict: Restrict results by recency (e.g., 'd7' for last 7 days)
        safe_search: Safe search level - 'off', 'medium', or 'high'
        tool_context: ADK tool context
        tool_config: Tool configuration containing API keys
        
    Returns:
        JSON string containing search results with sources for citation
    """
    log_identifier = "[web_search_google]"
    
    try:
        # Get API keys from tool_config
        config = tool_config or {}
        api_key = config.get("google_search_api_key")
        search_engine_id = config.get("google_cse_id")
        
        if not api_key or not search_engine_id:
            error_msg = "google_search_api_key or google_cse_id not configured in tool_config"
            log.error("%s %s", log_identifier, error_msg)
            return f"Error: {error_msg}"
        
        tool = GoogleSearchTool(
            api_key=api_key,
            search_engine_id=search_engine_id
        )
        
        result: SearchResult = await tool.search(
            query=query,
            max_results=max_results,
            search_type=search_type,  # type: ignore
            date_restrict=date_restrict,
            safe_search=safe_search,  # type: ignore
            **kwargs
        )
        
        if not result.success:
            log.error("%s Search failed: %s", log_identifier, result.error)
            return f"Error: {result.error}"
        
        log.info(
            "%s Search successful: %d results, %d images",
            log_identifier,
            len(result.organic),
            len(result.images)
        )
        
        # Format results as RAG-compatible metadata using DTOs for camelCase conversion
        rag_sources = []
        for i, source in enumerate(result.organic):
            rag_source = create_rag_source(
                citation_id=f"search{i}",
                file_id=f"web_search_{i}",
                filename=source.attribution or source.title,
                title=source.title,
                source_url=source.link,
                url=source.link,
                content_preview=source.snippet,
                relevance_score=1.0,
                source_type="web",
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                metadata={
                    "title": source.title,
                    "link": source.link,
                    "type": "web_search",
                    "favicon": f"https://www.google.com/s2/favicons?domain={source.link}&sz=32" if source.link else ""
                }
            )
            rag_sources.append(rag_source)
        
        # Return both JSON result and RAG metadata (with camelCase keys)
        rag_metadata = create_rag_search_result(
            query=query,
            search_type="web_search",
            timestamp=datetime.now(timezone.utc).isoformat(),
            sources=rag_sources
        )
        
        return {
            "result": result.model_dump_json(),
            "rag_metadata": rag_metadata
        }
        
    except Exception as e:
        log.exception("%s Unexpected error in Google search: %s", log_identifier, e)
        return f"Error executing Google search: {str(e)}"


# Tavily Search Tool Definition
web_search_tavily_tool_def = BuiltinTool(
    name="web_search_tavily",
    implementation=_web_search_tavily,
    description=(
        "Search the web using Tavily API for current information. "
        "Use this when you need up-to-date facts, news, or data. "
        "Always cite sources using the citation format provided in your instructions."
    ),
    category=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:web_search:execute"],
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (1-10)",
                "minimum": 1,
                "maximum": 10,
                "default": 5
            },
            "search_depth": {
                "type": "string",
                "enum": ["basic", "advanced"],
                "description": "Search depth: 'basic' for quick results, 'advanced' for comprehensive",
                "default": "basic"
            },
            "include_images": {
                "type": "boolean",
                "description": "Whether to include image results",
                "default": False
            },
            "include_answer": {
                "type": "boolean",
                "description": "Whether to include a direct answer",
                "default": False
            },
            "topic": {
                "type": "string",
                "enum": ["general", "news", "finance"],
                "description": "Search topic category"
            }
        },
        "required": ["query"]
    },
)

# Google Search Tool Definition
web_search_google_tool_def = BuiltinTool(
    name="web_search_google",
    implementation=_web_search_google,
    description=(
        "Search the web using Google Custom Search API. "
        "Use this when you need up-to-date information from Google. "
        "Always cite sources using the citation format provided in your instructions."
    ),
    category=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:web_search:execute"],
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (1-10)",
                "minimum": 1,
                "maximum": 10,
                "default": 5
            },
            "search_type": {
                "type": "string",
                "enum": ["image"],
                "description": "Set to 'image' for image search"
            },
            "date_restrict": {
                "type": "string",
                "description": "Restrict results by recency (e.g., 'd7' for last 7 days)"
            },
            "safe_search": {
                "type": "string",
                "enum": ["off", "medium", "high"],
                "description": "Safe search level"
            }
        },
        "required": ["query"]
    },
)

# Register tools with the registry only if API keys are available
import os

registered_tools = []

# Check if Tavily API key is configured
tavily_key = os.environ.get("TAVILY_API_KEY", "")
if tavily_key and tavily_key.strip():
    tool_registry.register(web_search_tavily_tool_def)
    registered_tools.append("web_search_tavily")
else:
    log.info("Tavily API key not configured, web_search_tavily tool will not be available")

# Check if Google Search API keys are configured
google_key = os.environ.get("GOOGLE_SEARCH_API_KEY", "")
google_cse = os.environ.get("GOOGLE_CSE_ID", "")
if google_key and google_key.strip() and google_cse and google_cse.strip():
    tool_registry.register(web_search_google_tool_def)
    registered_tools.append("web_search_google")
else:
    log.info("Google Search API keys not fully configured, web_search_google tool will not be available")

if registered_tools:
    log.info(f"Web search tools registered: {', '.join(registered_tools)}")
else:
    log.warning("No web search tools registered - neither Tavily nor Google Search API keys are configured")