"""
Web Search Tools for Solace Agent Mesh
Provides web search capabilities using Tavily, Google Custom Search, Exa, and Brave APIs
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from google.adk.tools import ToolContext

from ...tools.web_search import TavilySearchTool, GoogleSearchTool, ExaSearchTool, BraveSearchTool, SearchResult
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
        include_answer: Whether to include a direct answer from Tavily's LLM
        topic: Search topic - 'general', 'news', or 'finance'
        tool_context: ADK tool context
        tool_config: Tool configuration containing API keys
        
    Returns:
        JSON string containing search results with sources for citation
        
    Note:
        Tavily is optimized for text-based search. For dedicated image search,
        use web_search_google with search_type='image'.
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
            include_images=False,  # Tavily images are supplementary, not dedicated image search
            include_answer=include_answer,
            topic=topic,  # type: ignore
            **kwargs
        )
        
        if not result.success:
            log.error("%s Search failed: %s", log_identifier, result.error)
            return f"Error: {result.error}"
        
        log.info(
            "%s Search successful: %d organic results, %d news",
            log_identifier,
            len(result.organic),
            len(result.topStories)
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
        
        # Note: Tavily does not provide dedicated image search results
        # For image search, use web_search_google with search_type='image'
        
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
        
        # Add image results as RAG sources with special metadata
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
        "Always cite text sources using the citation format provided in your instructions. "
        "Note: Tavily is optimized for text-based search results. For dedicated image search, use web_search_google with search_type='image'."
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
            "include_answer": {
                "type": "boolean",
                "description": "Whether to include a direct answer from Tavily's LLM",
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

async def _web_search_exa(
    query: str,
    max_results: int = 10,
    search_type: Optional[str] = "auto",
    category: Optional[str] = None,
    start_published_date: Optional[str] = None,
    end_published_date: Optional[str] = None,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    include_text: Optional[List[str]] = None,
    exclude_text: Optional[List[str]] = None,
    contents_highlights: bool = False,
    contents_summary: bool = False,
    livecrawl: Optional[str] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> str:
    """
    Search the web using Exa's AI-powered search engine.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (1-100)
        search_type: Search type - 'neural', 'fast', 'auto', or 'deep'
        category: Data category to focus on (e.g., 'research paper', 'news', 'company')
        start_published_date: Only results published after this date (ISO 8601)
        end_published_date: Only results published before this date (ISO 8601)
        include_domains: List of domains to include in results
        exclude_domains: List of domains to exclude from results
        include_text: Strings that must be present in results
        exclude_text: Strings that must not be present in results
        contents_highlights: Whether to include highlighted snippets
        contents_summary: Whether to include AI-generated summaries
        livecrawl: Livecrawling option - 'never', 'fallback', 'always', 'preferred'
        tool_context: ADK tool context
        tool_config: Tool configuration containing API keys
        
    Returns:
        JSON string containing search results with sources for citation
        
    Note:
        Exa uses embeddings-based neural search for intelligent result ranking.
        Deep search provides comprehensive results with query expansion.
    """
    log_identifier = "[web_search_exa]"
    
    try:
        # Get API key from tool_config
        config = tool_config or {}
        api_key = config.get("exa_api_key")
        
        if not api_key:
            error_msg = "exa_api_key not configured in tool_config"
            log.error("%s %s", log_identifier, error_msg)
            return f"Error: {error_msg}"
        
        tool = ExaSearchTool(api_key=api_key)
        
        result: SearchResult = await tool.search(
            query=query,
            max_results=max_results,
            search_type=search_type,  # type: ignore
            category=category,  # type: ignore
            start_published_date=start_published_date,
            end_published_date=end_published_date,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            include_text=include_text,
            exclude_text=exclude_text,
            contents_highlights=contents_highlights,
            contents_summary=contents_summary,
            livecrawl=livecrawl,  # type: ignore
            **kwargs
        )
        
        if not result.success:
            log.error("%s Search failed: %s", log_identifier, result.error)
            return f"Error: {result.error}"
        
        log.info(
            "%s Search successful: %d organic results, %d images",
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
                    "provider": "exa",
                    "favicon": f"https://www.google.com/s2/favicons?domain={source.link}&sz=32" if source.link else ""
                }
            )
            rag_sources.append(rag_source)
        
        # Add image results as RAG sources with special metadata
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
                    "provider": "exa",
                }
            )
            rag_sources.append(image_source)
        
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
        log.exception("%s Unexpected error in Exa search: %s", log_identifier, e)
        return f"Error executing Exa search: {str(e)}"


# Exa Search Tool Definition
web_search_exa_tool_def = BuiltinTool(
    name="web_search_exa",
    implementation=_web_search_exa,
    description=(
        "Search the web using Exa's AI-powered search engine. "
        "Exa uses embeddings-based neural search to find the most relevant results. "
        "Supports deep search for comprehensive results with query expansion. "
        "Can filter by category (research papers, news, companies, GitHub, tweets, etc.) and date ranges. "
        "Always cite text sources using the citation format provided in your instructions."
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
                "description": "Maximum number of results (1-100)",
                "minimum": 1,
                "maximum": 100,
                "default": 10
            },
            "search_type": {
                "type": "string",
                "enum": ["neural", "fast", "auto", "deep"],
                "description": "Search type: 'neural' for embeddings-based, 'auto' for intelligent selection (default), 'deep' for comprehensive with query expansion",
                "default": "auto"
            },
            "category": {
                "type": "string",
                "enum": [
                    "company", "research paper", "news", "pdf", "github",
                    "tweet", "personal site", "linkedin profile", "financial report"
                ],
                "description": "Data category to focus on for more targeted results"
            },
            "start_published_date": {
                "type": "string",
                "description": "Only results published after this date (ISO 8601 format, e.g., '2024-01-01T00:00:00.000Z')"
            },
            "end_published_date": {
                "type": "string",
                "description": "Only results published before this date (ISO 8601 format)"
            },
            "include_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of domains to include in results (e.g., ['arxiv.org', 'github.com'])"
            },
            "exclude_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of domains to exclude from results"
            },
            "contents_highlights": {
                "type": "boolean",
                "description": "Whether to include highlighted snippets from each result",
                "default": False
            },
            "contents_summary": {
                "type": "boolean",
                "description": "Whether to include AI-generated summaries for each result",
                "default": False
            }
        },
        "required": ["query"]
    },
)

async def _web_search_brave(
    query: str,
    max_results: int = 10,
    country: Optional[str] = "US",
    search_lang: Optional[str] = "en",
    safesearch: Optional[str] = "moderate",
    freshness: Optional[str] = None,
    result_filter: Optional[str] = None,
    extra_snippets: bool = False,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> str:
    """
    Search the web using Brave Search API.
    
    Args:
        query: The search query string (max 400 characters)
        max_results: Maximum number of results to return (1-20)
        country: Two-letter country code for results origin (e.g., 'US', 'GB')
        search_lang: Two-letter language code for results (e.g., 'en', 'fr')
        safesearch: Safe search level - 'off', 'moderate', 'strict'
        freshness: Time filter - 'pd' (24h), 'pw' (7d), 'pm' (31d), 'py' (365d), or date range
        result_filter: Comma-delimited result types to include (e.g., 'web,news,videos')
        extra_snippets: Get up to 5 additional snippets per result
        tool_context: ADK tool context
        tool_config: Tool configuration containing API keys
        
    Returns:
        JSON string containing search results with sources for citation
        
    Note:
        Brave Search is a privacy-focused search engine that provides web results,
        news, videos, FAQs, and discussions.
    """
    log_identifier = "[web_search_brave]"
    
    try:
        # Get API key from tool_config
        config = tool_config or {}
        api_key = config.get("brave_api_key")
        
        if not api_key:
            error_msg = "brave_api_key not configured in tool_config"
            log.error("%s %s", log_identifier, error_msg)
            return f"Error: {error_msg}"
        
        tool = BraveSearchTool(api_key=api_key)
        
        result: SearchResult = await tool.search(
            query=query,
            max_results=max_results,
            country=country,
            search_lang=search_lang,
            safesearch=safesearch,  # type: ignore
            freshness=freshness,
            result_filter=result_filter,
            extra_snippets=extra_snippets,
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
                    "provider": "brave",
                    "favicon": f"https://www.google.com/s2/favicons?domain={source.link}&sz=32" if source.link else ""
                }
            )
            rag_sources.append(rag_source)
        
        # Add news results as RAG sources
        for i, news in enumerate(result.topStories):
            news_source = create_rag_source(
                citation_id=f"news{i}",
                file_id=f"web_search_news_{i}",
                filename=news.attribution or news.title,
                title=news.title,
                source_url=news.link,
                url=news.link,
                content_preview=news.snippet,
                relevance_score=1.0,
                source_type="news",
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                metadata={
                    "title": news.title,
                    "link": news.link,
                    "type": "news",
                    "provider": "brave",
                    "favicon": f"https://www.google.com/s2/favicons?domain={news.link}&sz=32" if news.link else ""
                }
            )
            rag_sources.append(news_source)
        
        # Add image/video results as RAG sources with special metadata
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
                    "provider": "brave",
                }
            )
            rag_sources.append(image_source)
        
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
        log.exception("%s Unexpected error in Brave search: %s", log_identifier, e)
        return f"Error executing Brave search: {str(e)}"


# Brave Search Tool Definition
web_search_brave_tool_def = BuiltinTool(
    name="web_search_brave",
    implementation=_web_search_brave,
    description=(
        "Search the web using Brave Search, a privacy-focused search engine. "
        "Provides web results, news, videos, FAQs, and discussions. "
        "Supports freshness filtering (time-based), country/language preferences, and safe search. "
        "Always cite text sources using the citation format provided in your instructions."
    ),
    category=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:web_search:execute"],
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query (max 400 characters)"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (1-20)",
                "minimum": 1,
                "maximum": 20,
                "default": 10
            },
            "country": {
                "type": "string",
                "description": "Two-letter country code for results origin (e.g., 'US', 'GB', 'DE')",
                "default": "US"
            },
            "search_lang": {
                "type": "string",
                "description": "Two-letter language code for results (e.g., 'en', 'fr', 'de')",
                "default": "en"
            },
            "safesearch": {
                "type": "string",
                "enum": ["off", "moderate", "strict"],
                "description": "Safe search level: 'off' for no filtering, 'moderate' for explicit content filtering, 'strict' for all adult content filtering",
                "default": "moderate"
            },
            "freshness": {
                "type": "string",
                "description": "Time filter: 'pd' (past day/24h), 'pw' (past week/7d), 'pm' (past month/31d), 'py' (past year/365d), or date range 'YYYY-MM-DDtoYYYY-MM-DD'"
            },
            "result_filter": {
                "type": "string",
                "description": "Comma-delimited result types to include: 'discussions', 'faq', 'infobox', 'news', 'videos', 'web', 'locations'"
            },
            "extra_snippets": {
                "type": "boolean",
                "description": "Get up to 5 additional snippets per result for more context",
                "default": False
            }
        },
        "required": ["query"]
    },
)

# Always register tools - they will check for API keys at runtime via tool_config
tool_registry.register(web_search_tavily_tool_def)
tool_registry.register(web_search_google_tool_def)
tool_registry.register(web_search_exa_tool_def)
tool_registry.register(web_search_brave_tool_def)

log.info("Web search tools registered: web_search_tavily, web_search_google, web_search_exa, web_search_brave")
log.info("Note: Tools will check for API keys in tool_config at runtime")