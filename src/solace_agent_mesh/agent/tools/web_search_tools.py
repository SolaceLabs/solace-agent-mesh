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

# Global search turn counter to ensure unique citation IDs across multiple searches
# Key: session_id, Value: turn counter
_search_turn_counter: Dict[str, int] = {}


def _get_next_search_turn(session_id: str = "default") -> int:
    """
    Get the next search turn number for a session to ensure unique citation IDs.
    
    Each search within a session gets a unique turn number, so citations from
    different searches never collide (e.g., s0r0, s0r1 for first search,
    s1r0, s1r1 for second search).
    """
    global _search_turn_counter
    if session_id not in _search_turn_counter:
        _search_turn_counter[session_id] = 0
    turn = _search_turn_counter[session_id]
    _search_turn_counter[session_id] += 1
    return turn


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
        
        # Get unique search turn for this search to prevent citation ID collisions
        # across multiple searches in the same session
        session_id = "default"
        if tool_context:
            try:
                # Try to get session ID from tool context for per-session tracking
                session_id = getattr(tool_context, 'session_id', None) or "default"
            except Exception:
                pass
        
        search_turn = _get_next_search_turn(session_id)
        citation_prefix = f"s{search_turn}r"  # e.g., s0r0, s0r1 for first search; s1r0, s1r1 for second
        
        log.info(
            "%s Search successful: %d results, %d images (turn=%d, citation_prefix=%s)",
            log_identifier,
            len(result.organic),
            len(result.images),
            search_turn,
            citation_prefix
        )
        
        rag_sources = []
        valid_citation_ids = []
        
        # Log citation-to-source mapping for debugging
        log.info("%s === CITATION TO SOURCE MAPPING (turn %d) ===", log_identifier, search_turn)
        
        for i, source in enumerate(result.organic):
            citation_id = f"{citation_prefix}{i}"
            valid_citation_ids.append(citation_id)
            
            # Log each citation mapping
            log.info(
                "%s Citation [[cite:%s]] -> URL: %s | Title: %s",
                log_identifier,
                citation_id,
                source.link,
                source.title[:50] if source.title else "N/A"
            )
            
            rag_source = create_rag_source(
                citation_id=citation_id,
                file_id=f"web_search_{search_turn}_{i}",
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
        
        log.info("%s === END CITATION MAPPING ===", log_identifier)
        log.info("%s Valid citation IDs for this search: %s", log_identifier, valid_citation_ids)
        
        for i, image in enumerate(result.images):
            image_citation_id = f"img{search_turn}r{i}"
            image_source = create_rag_source(
                citation_id=image_citation_id,
                file_id=f"web_search_image_{search_turn}_{i}",
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
            "rag_metadata": rag_metadata,
            "valid_citation_ids": valid_citation_ids,
            "num_results": len(result.organic),
            "search_turn": search_turn
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