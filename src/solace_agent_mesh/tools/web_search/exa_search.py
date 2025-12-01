"""Exa search tool implementation.

Exa is an AI-powered search engine that provides intelligent web search
with embeddings-based neural search and comprehensive deep search capabilities.
"""

import httpx
import logging
from typing import Literal, Optional, List, Dict, Any
from .base import WebSearchTool
from .models import SearchResult, SearchSource, ImageResult

logger = logging.getLogger(__name__)


class ExaSearchTool(WebSearchTool):
    """Exa search API implementation.
    
    Exa provides intelligent web search using embeddings-based neural search
    and other techniques to find the most relevant results. It supports:
    - Neural search (embeddings-based)
    - Deep search (comprehensive with query expansion)
    - Auto mode (intelligently combines methods)
    - Fast mode (streamlined search)
    - Category filtering (company, research paper, news, etc.)
    - Content retrieval (text, highlights, summaries)
    """
    
    def __init__(self, api_key: str, **kwargs):
        """Initialize Exa search tool.
        
        Args:
            api_key: Exa API key
            **kwargs: Additional configuration
        """
        super().__init__(api_key=api_key, **kwargs)
        self.base_url = "https://api.exa.ai/search"
        
        if not self.api_key:
            raise ValueError("Exa API key is required")
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        search_depth: Literal["basic", "advanced"] = "basic",
        search_type: Optional[Literal["neural", "fast", "auto", "deep"]] = "auto",
        category: Optional[Literal[
            "company", "research paper", "news", "pdf", "github",
            "tweet", "personal site", "linkedin profile", "financial report"
        ]] = None,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        start_crawl_date: Optional[str] = None,
        end_crawl_date: Optional[str] = None,
        start_published_date: Optional[str] = None,
        end_published_date: Optional[str] = None,
        include_text: Optional[List[str]] = None,
        exclude_text: Optional[List[str]] = None,
        include_contents: bool = True,
        contents_text: bool = True,
        contents_highlights: bool = False,
        contents_summary: bool = False,
        highlights_per_url: int = 1,
        num_sentences: int = 3,
        summary_query: Optional[str] = None,
        livecrawl: Optional[Literal["never", "fallback", "always", "preferred"]] = None,
        moderation: bool = False,
        user_location: Optional[str] = None,
        additional_queries: Optional[List[str]] = None,
        **kwargs
    ) -> SearchResult:
        """Execute Exa search.
        
        Args:
            query: Search query string
            max_results: Maximum number of results (1-100)
            search_depth: 'basic' maps to 'auto', 'advanced' maps to 'deep'
            search_type: Exa search type - 'neural', 'fast', 'auto', or 'deep'
            category: Data category to focus on
            include_domains: List of domains to include
            exclude_domains: List of domains to exclude
            start_crawl_date: Results crawled after this date (ISO 8601)
            end_crawl_date: Results crawled before this date (ISO 8601)
            start_published_date: Results published after this date (ISO 8601)
            end_published_date: Results published before this date (ISO 8601)
            include_text: Strings that must be present in results
            exclude_text: Strings that must not be present in results
            include_contents: Whether to include page contents
            contents_text: Include full page text
            contents_highlights: Include highlighted snippets
            contents_summary: Include AI-generated summary
            highlights_per_url: Number of highlights per result
            num_sentences: Number of sentences per highlight
            summary_query: Custom query for summary generation
            livecrawl: Livecrawling option
            moderation: Enable content moderation
            user_location: Two-letter ISO country code
            additional_queries: Additional query variations for deep search
            **kwargs: Additional parameters
            
        Returns:
            SearchResult object
        """
        try:
            # Map search_depth to Exa search type if search_type not explicitly set
            if search_type is None:
                search_type = "deep" if search_depth == "advanced" else "auto"
            
            # Exa allows max 100 results
            num_results = min(max(max_results, 1), 100)
            
            # Build request payload
            payload: Dict[str, Any] = {
                "query": query,
                "numResults": num_results,
                "type": search_type,
            }
            
            # Add optional parameters
            if category:
                payload["category"] = category
            if user_location:
                payload["userLocation"] = user_location
            if include_domains:
                payload["includeDomains"] = include_domains
            if exclude_domains:
                payload["excludeDomains"] = exclude_domains
            if start_crawl_date:
                payload["startCrawlDate"] = start_crawl_date
            if end_crawl_date:
                payload["endCrawlDate"] = end_crawl_date
            if start_published_date:
                payload["startPublishedDate"] = start_published_date
            if end_published_date:
                payload["endPublishedDate"] = end_published_date
            if include_text:
                payload["includeText"] = include_text
            if exclude_text:
                payload["excludeText"] = exclude_text
            if moderation:
                payload["moderation"] = moderation
            if additional_queries and search_type == "deep":
                payload["additionalQueries"] = additional_queries
            
            # Build contents configuration
            if include_contents:
                contents_config: Dict[str, Any] = {}
                
                if contents_text:
                    contents_config["text"] = True
                
                if contents_highlights:
                    contents_config["highlights"] = {
                        "numSentences": num_sentences,
                        "highlightsPerUrl": highlights_per_url,
                    }
                
                if contents_summary:
                    summary_config: Dict[str, Any] = {}
                    if summary_query:
                        summary_config["query"] = summary_query
                    contents_config["summary"] = summary_config if summary_config else True
                
                if livecrawl:
                    contents_config["livecrawl"] = livecrawl
                
                if contents_config:
                    payload["contents"] = contents_config
            
            logger.info(f"Executing Exa search: query='{query}', type={search_type}, num={num_results}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    json=payload,
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    timeout=60.0  # Longer timeout for deep search
                )
                
                if response.status_code != 200:
                    error_msg = f"Exa API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg += f" - {error_data.get('error', error_data.get('message', ''))}"
                    except Exception:
                        error_msg += f" - {response.text}"
                    
                    logger.error(error_msg)
                    return SearchResult(
                        success=False,
                        query=query,
                        error=error_msg
                    )
                
                data = response.json()
                
                # Transform results to our format
                organic = []
                images = []
                
                for result in data.get("results", []):
                    try:
                        # Build snippet from available content
                        snippet = ""
                        
                        # Prefer highlights if available
                        highlights = result.get("highlights", [])
                        if highlights:
                            snippet = " ".join(highlights)
                        # Fall back to summary
                        elif result.get("summary"):
                            snippet = result["summary"]
                        # Fall back to text preview
                        elif result.get("text"):
                            text = result["text"]
                            # Take first 500 chars as snippet
                            snippet = text[:500] + "..." if len(text) > 500 else text
                        
                        source = SearchSource(
                            link=result["url"],
                            title=result.get("title", ""),
                            snippet=snippet,
                            attribution=self._extract_domain(result["url"]),
                            imageUrl=result.get("image")
                        )
                        organic.append(source)
                        
                        # If result has an image, also add to images list
                        if result.get("image"):
                            image = ImageResult(
                                imageUrl=result["image"],
                                title=result.get("title", ""),
                                link=result["url"]
                            )
                            images.append(image)
                            
                    except Exception as e:
                        logger.warning(f"Failed to parse Exa search result: {e}")
                        continue
                
                logger.info(f"Exa search successful: {len(organic)} results")
                
                # Build metadata
                metadata = {
                    "search_engine": "exa",
                    "search_type": search_type,
                    "resolved_search_type": data.get("resolvedSearchType"),
                    "request_id": data.get("requestId"),
                }
                
                # Include cost information if available
                if "costDollars" in data:
                    metadata["cost_dollars"] = data["costDollars"]
                
                # Include context string if available
                answer_box = None
                if data.get("context"):
                    answer_box = data["context"]
                
                return SearchResult(
                    success=True,
                    query=query,
                    organic=organic,
                    images=images,
                    answerBox=answer_box,
                    metadata=metadata
                )
                
        except httpx.TimeoutException:
            error_msg = "Exa search timed out"
            logger.error(error_msg)
            return SearchResult(
                success=False,
                query=query,
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Exa search failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return SearchResult(
                success=False,
                query=query,
                error=error_msg
            )
    
    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract clean domain from URL.
        
        Args:
            url: Full URL
            
        Returns:
            Clean domain name
        """
        try:
            # Remove protocol
            domain = url.replace("https://", "").replace("http://", "")
            # Get first part (domain)
            domain = domain.split("/")[0]
            # Remove www.
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return url
    
    def get_tool_definition(self) -> dict:
        """Get the tool definition for LLM function calling.
        
        Returns:
            Dictionary containing the tool definition
        """
        return {
            "type": "function",
            "function": {
                "name": "web_search_exa",
                "description": (
                    "Search the web using Exa's AI-powered search engine. "
                    "Exa uses embeddings-based neural search to find the most relevant results. "
                    "Supports deep search for comprehensive results with query expansion. "
                    "Can filter by category (research papers, news, companies, etc.) and date ranges. "
                    "Always cite sources using the citation format."
                ),
                "parameters": {
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
                            "description": "Search type: 'neural' for embeddings-based, 'auto' for intelligent selection, 'deep' for comprehensive with query expansion",
                            "default": "auto"
                        },
                        "category": {
                            "type": "string",
                            "enum": [
                                "company", "research paper", "news", "pdf", "github",
                                "tweet", "personal site", "linkedin profile", "financial report"
                            ],
                            "description": "Data category to focus on"
                        },
                        "start_published_date": {
                            "type": "string",
                            "description": "Only results published after this date (ISO 8601 format)"
                        },
                        "end_published_date": {
                            "type": "string",
                            "description": "Only results published before this date (ISO 8601 format)"
                        }
                    },
                    "required": ["query"]
                }
            }
        }