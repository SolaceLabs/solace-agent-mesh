"""
Web Search Tools for Solace Agent Mesh
Provides web search capabilities using Tavily and Google Custom Search APIs
"""

import os
import logging
from typing import Any, Dict, Optional

from ...tools.web_search import TavilySearchTool, GoogleSearchTool, SearchResult
from .tool_definition import BuiltinTool
from .registry import tool_registry

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
        
    Returns:
        JSON string containing search results with sources for citation
    """
    log_identifier = "[web_search_tavily]"
    
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            error_msg = "TAVILY_API_KEY environment variable not set"
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
        
        # Format results as RAG-compatible metadata for citation rendering
        rag_sources = []
        for i, source in enumerate(result.organic):
            rag_sources.append({
                "citation_id": f"search{i}",
                "file_id": f"web_search_{i}",
                "filename": source.attribution or source.title,
                "content_preview": source.snippet,
                "relevance_score": 1.0,
                "source_url": source.link,
                "metadata": {
                    "title": source.title,
                    "link": source.link,
                    "type": "web_search"
                }
            })
        
        # Return both JSON result and RAG metadata
        return {
            "result": result.model_dump_json(),
            "rag_metadata": {
                "query": query,
                "search_type": "web_search",
                "timestamp": "now",
                "sources": rag_sources
            }
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
        
    Returns:
        JSON string containing search results with sources for citation
    """
    log_identifier = "[web_search_google]"
    
    try:
        api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        search_engine_id = os.getenv("GOOGLE_CSE_ID")
        
        if not api_key or not search_engine_id:
            error_msg = "GOOGLE_SEARCH_API_KEY or GOOGLE_CSE_ID environment variable not set"
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
        
        # Format results as RAG-compatible metadata for citation rendering
        rag_sources = []
        for i, source in enumerate(result.organic):
            rag_sources.append({
                "citation_id": f"search{i}",
                "file_id": f"web_search_{i}",
                "filename": source.attribution or source.title,
                "content_preview": source.snippet,
                "relevance_score": 1.0,
                "source_url": source.link,
                "metadata": {
                    "title": source.title,
                    "link": source.link,
                    "type": "web_search"
                }
            })
        
        # Return both JSON result and RAG metadata
        return {
            "result": result.model_dump_json(),
            "rag_metadata": {
                "query": query,
                "search_type": "web_search",
                "timestamp": "now",
                "sources": rag_sources
            }
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

# Register tools with the registry
tool_registry.register(web_search_tavily_tool_def)
tool_registry.register(web_search_google_tool_def)

log.info("Web search tools registered: web_search_tavily, web_search_google")