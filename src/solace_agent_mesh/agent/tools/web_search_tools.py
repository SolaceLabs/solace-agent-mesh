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

# State key for tracking search turns within a task/session
_SEARCH_TURN_STATE_KEY = "web_search_turn_counter"


def _get_next_search_turn(tool_context: Optional[ToolContext]) -> int:
    """
    Get the next search turn number using tool context state.
    
    This approach stores the turn counter in the tool context state, which is:
    - Per-task/session scoped (not global)
    - Automatically cleaned up when the task ends
    
    Each search within a task gets a unique turn number, so citations from
    different searches never collide (e.g., s0r0, s0r1 for first search,
    s1r0, s1r1 for second search).
    """
    if not tool_context:
        # Fallback: return 0 if no context (shouldn't happen in practice)
        log.warning("[web_search] No tool_context provided, using turn=0")
        return 0
    
    # Get current turn from state, defaulting to 0
    current_turn = tool_context.state.get(_SEARCH_TURN_STATE_KEY, 0)
    
    # Increment for next search
    tool_context.state[_SEARCH_TURN_STATE_KEY] = current_turn + 1
    
    return current_turn


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
        # Uses tool context state (per-task scoped, automatically cleaned up)
        search_turn = _get_next_search_turn(tool_context)
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
        log.debug("%s === CITATION TO SOURCE MAPPING (turn %d) ===", log_identifier, search_turn)
        
        for i, source in enumerate(result.organic):
            citation_id = f"{citation_prefix}{i}"
            valid_citation_ids.append(citation_id)
            
            # Log each citation mapping at debug level
            log.debug(
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
        
        log.debug("%s === END CITATION MAPPING ===", log_identifier)
        log.debug("%s Valid citation IDs for this search: %s", log_identifier, valid_citation_ids)
        
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
        
        # Build a formatted result string that clearly associates each citation ID with its content
        # This helps the LLM correctly match citations to facts
        formatted_results = []
        formatted_results.append(f"=== SEARCH RESULTS (Turn {search_turn}) ===")
        formatted_results.append(f"Query: {query}")
        formatted_results.append(f"Valid citation IDs: {', '.join(valid_citation_ids)}")
        formatted_results.append("")
        
        for i, source in enumerate(result.organic):
            citation_id = f"{citation_prefix}{i}"
            formatted_results.append(f"--- RESULT {i+1} ---")
            formatted_results.append(f"CITATION ID: [[cite:{citation_id}]]")
            formatted_results.append(f"TITLE: {source.title}")
            formatted_results.append(f"URL: {source.link}")
            formatted_results.append(f"CONTENT: {source.snippet}")
            formatted_results.append(f"USE [[cite:{citation_id}]] to cite facts from THIS result only")
            formatted_results.append("")
        
        formatted_results.append("=== END SEARCH RESULTS ===")
        formatted_results.append("")
        formatted_results.append("IMPORTANT: Each citation ID is UNIQUE to its result.")
        formatted_results.append("Only use a citation ID for facts that appear in THAT specific result's CONTENT.")
        
        return {
            "result": result.model_dump_json(),
            "formatted_results": "\n".join(formatted_results),
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