"""
Web Search Tools for Solace Agent Mesh
Provides web search capabilities using Google Custom Search API.

For other search providers (e.g., Exa, Brave, Tavily), please use the corresponding
plugins from the solace-agent-mesh-plugins repository.
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from google.adk.tools import ToolContext

from ...tools.web_search import GoogleSearchTool, SearchResult
from .tool_definition import BuiltinTool
from .registry import tool_registry
from ...common.rag_dto import create_rag_source, create_rag_search_result

log = logging.getLogger(__name__)

CATEGORY_NAME = "web_search"
CATEGORY_DESCRIPTION = "Tools for searching the web and retrieving current information"


async def web_search_google(
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
            search_type=search_type,
            date_restrict=date_restrict,
            safe_search=safe_search,
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
        
        for i, image in enumerate(result.images):
            image_source = create_rag_source(
                citation_id=f"image{i}",
                file_id=f"web_search_image_{i}",
                filename=image.title or f"Image {i+1}",
                title=image.title,
                source_url=image.link,
                url=image.link,
                content_preview=image.title or "",
                relevance_score=1.0,
                source_type="image",
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                metadata={
                    "title": image.title,
                    "link": image.link,
                    "imageUrl": image.imageUrl,
                    "type": "image",
                }
            )
            rag_sources.append(image_source)
        
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


web_search_google_tool_def = BuiltinTool(
    name="web_search_google",
    implementation=web_search_google,
    description=(
        "Search the web using Google Custom Search API. "
        "Use this when you need up-to-date information from Google. "
        "Always cite text sources using the citation format provided in your instructions. "
        "IMPORTANT: Image results will be displayed automatically in the UI - do NOT cite images, do NOT mention image URLs, and do NOT use citation markers like [[cite:imageX]] for images in your response text."
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

tool_registry.register(web_search_google_tool_def)

log.info("Web search tools registered: web_search_google")
log.info("Note: For Exa, Brave, and Tavily search, use plugins from solace-agent-mesh-plugins")