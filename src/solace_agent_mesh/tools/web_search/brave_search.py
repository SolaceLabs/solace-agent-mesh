"""Brave Web Search API implementation.

Brave Search is a privacy-focused search engine that provides web search
results through a REST API.
"""

import httpx
import logging
from typing import Literal, Optional, List, Dict, Any
from .base import WebSearchTool
from .models import SearchResult, SearchSource, ImageResult

logger = logging.getLogger(__name__)


class BraveSearchTool(WebSearchTool):
    """Brave Web Search API implementation.
    
    Brave Search provides privacy-focused web search with support for:
    - Web search results with snippets
    - News results
    - Video results
    - FAQ results
    - Discussions (forum results)
    - Infobox (knowledge panel)
    - Freshness filtering (time-based)
    - Safe search filtering
    - Country and language preferences
    - Goggles for custom re-ranking
    """
    
    def __init__(self, api_key: str, **kwargs):
        """Initialize Brave search tool.
        
        Args:
            api_key: Brave Search API subscription token
            **kwargs: Additional configuration
        """
        super().__init__(api_key=api_key, **kwargs)
        self.base_url = "https://api.search.brave.com/res/v1/web/search"
        
        if not self.api_key:
            raise ValueError("Brave Search API key is required")
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        search_depth: Literal["basic", "advanced"] = "basic",
        country: Optional[str] = "US",
        search_lang: Optional[str] = "en",
        ui_lang: Optional[str] = "en-US",
        offset: int = 0,
        safesearch: Optional[Literal["off", "moderate", "strict"]] = "moderate",
        freshness: Optional[str] = None,
        text_decorations: bool = True,
        spellcheck: bool = True,
        result_filter: Optional[str] = None,
        goggles: Optional[List[str]] = None,
        units: Optional[Literal["metric", "imperial"]] = None,
        extra_snippets: bool = False,
        summary: bool = False,
        **kwargs
    ) -> SearchResult:
        """Execute Brave Web Search.
        
        Args:
            query: Search query string (max 400 chars, 50 words)
            max_results: Maximum number of results (1-20)
            search_depth: Not used for Brave (kept for interface compatibility)
            country: Two-letter country code for results origin
            search_lang: Two-letter language code for results
            ui_lang: UI language preference (e.g., 'en-US')
            offset: Zero-based offset for pagination (0-9)
            safesearch: Safe search level - 'off', 'moderate', 'strict'
            freshness: Time filter - 'pd' (24h), 'pw' (7d), 'pm' (31d), 'py' (365d), or date range
            text_decorations: Include decoration markers in snippets
            spellcheck: Enable spellcheck on query
            result_filter: Comma-delimited result types to include
            goggles: List of Goggle URLs or definitions for custom re-ranking
            units: Measurement units - 'metric' or 'imperial'
            extra_snippets: Get up to 5 additional snippets per result
            summary: Enable summary generation
            **kwargs: Additional parameters
            
        Returns:
            SearchResult object
        """
        try:
            # Brave allows max 20 results per request
            count = min(max(max_results, 1), 20)
            
            # Build query parameters
            params: Dict[str, Any] = {
                "q": query[:400],  # Max 400 characters
                "count": count,
            }
            
            # Add optional parameters
            if country:
                params["country"] = country
            if search_lang:
                params["search_lang"] = search_lang
            if ui_lang:
                params["ui_lang"] = ui_lang
            if offset > 0:
                params["offset"] = min(offset, 9)  # Max offset is 9
            if safesearch:
                params["safesearch"] = safesearch
            if freshness:
                params["freshness"] = freshness
            if not text_decorations:
                params["text_decorations"] = False
            if not spellcheck:
                params["spellcheck"] = False
            if result_filter:
                params["result_filter"] = result_filter
            if goggles:
                # Brave supports multiple goggles parameters
                for goggle in goggles:
                    if "goggles" not in params:
                        params["goggles"] = goggle
                    # Note: httpx handles list params differently, we'll handle this in the request
            if units:
                params["units"] = units
            if extra_snippets:
                params["extra_snippets"] = True
            if summary:
                params["summary"] = True
            
            logger.info(f"Executing Brave search: query='{query[:50]}...', count={count}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": self.api_key
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_msg = f"Brave API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg += f" - {error_data.get('message', error_data.get('error', ''))}"
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
                top_stories = []
                answer_box = None
                
                # Process web results
                web_results = data.get("web", {}).get("results", [])
                for result in web_results:
                    try:
                        # Build snippet from description and extra snippets
                        snippet = result.get("description", "")
                        extra = result.get("extra_snippets", [])
                        if extra:
                            snippet += " " + " ".join(extra)
                        
                        source = SearchSource(
                            link=result["url"],
                            title=result.get("title", ""),
                            snippet=snippet,
                            attribution=self._extract_domain(result["url"]),
                            imageUrl=result.get("thumbnail", {}).get("src") if result.get("thumbnail") else None
                        )
                        organic.append(source)
                    except Exception as e:
                        logger.warning(f"Failed to parse Brave web result: {e}")
                        continue
                
                # Process news results
                news_results = data.get("news", {}).get("results", [])
                for result in news_results:
                    try:
                        source = SearchSource(
                            link=result["url"],
                            title=result.get("title", ""),
                            snippet=result.get("description", ""),
                            attribution=result.get("meta_url", {}).get("hostname", self._extract_domain(result["url"])),
                            imageUrl=result.get("thumbnail", {}).get("src") if result.get("thumbnail") else None
                        )
                        top_stories.append(source)
                    except Exception as e:
                        logger.warning(f"Failed to parse Brave news result: {e}")
                        continue
                
                # Process video results
                video_results = data.get("videos", {}).get("results", [])
                for result in video_results:
                    try:
                        # Add videos as images with video metadata
                        if result.get("thumbnail", {}).get("src"):
                            image = ImageResult(
                                imageUrl=result["thumbnail"]["src"],
                                title=result.get("title", ""),
                                link=result["url"]
                            )
                            images.append(image)
                    except Exception as e:
                        logger.warning(f"Failed to parse Brave video result: {e}")
                        continue
                
                # Process infobox (knowledge panel)
                infobox = data.get("infobox")
                if infobox:
                    answer_box = infobox.get("description", "")
                    if infobox.get("long_desc"):
                        answer_box = infobox["long_desc"]
                
                # Process FAQ results
                faq_results = data.get("faq", {}).get("results", [])
                for result in faq_results:
                    try:
                        source = SearchSource(
                            link=result.get("url", ""),
                            title=result.get("question", ""),
                            snippet=result.get("answer", ""),
                            attribution=self._extract_domain(result.get("url", ""))
                        )
                        organic.append(source)
                    except Exception as e:
                        logger.warning(f"Failed to parse Brave FAQ result: {e}")
                        continue
                
                # Process discussions
                discussions = data.get("discussions", {}).get("results", [])
                for result in discussions:
                    try:
                        source = SearchSource(
                            link=result["url"],
                            title=result.get("title", ""),
                            snippet=result.get("description", ""),
                            attribution=self._extract_domain(result["url"])
                        )
                        organic.append(source)
                    except Exception as e:
                        logger.warning(f"Failed to parse Brave discussion result: {e}")
                        continue
                
                logger.info(f"Brave search successful: {len(organic)} web results, {len(top_stories)} news")
                
                # Build metadata
                metadata: Dict[str, Any] = {
                    "search_engine": "brave",
                    "country": country,
                    "search_lang": search_lang,
                }
                
                # Include query info if available
                query_info = data.get("query", {})
                if query_info:
                    metadata["original_query"] = query_info.get("original")
                    metadata["altered_query"] = query_info.get("altered")
                    metadata["spellcheck_off"] = query_info.get("spellcheck_off")
                
                # Include summarizer if available
                summarizer = data.get("summarizer")
                if summarizer and summarizer.get("key"):
                    metadata["summarizer_key"] = summarizer["key"]
                
                return SearchResult(
                    success=True,
                    query=query,
                    organic=organic,
                    topStories=top_stories,
                    images=images,
                    answerBox=answer_box,
                    metadata=metadata
                )
                
        except httpx.TimeoutException:
            error_msg = "Brave search timed out"
            logger.error(error_msg)
            return SearchResult(
                success=False,
                query=query,
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Brave search failed: {str(e)}"
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
                "name": "web_search_brave",
                "description": (
                    "Search the web using Brave Search, a privacy-focused search engine. "
                    "Supports web results, news, videos, FAQs, and discussions. "
                    "Can filter by freshness (time), country, language, and safe search level. "
                    "Always cite sources using the citation format."
                ),
                "parameters": {
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
                        "freshness": {
                            "type": "string",
                            "description": "Time filter: 'pd' (24h), 'pw' (7d), 'pm' (31d), 'py' (365d), or date range 'YYYY-MM-DDtoYYYY-MM-DD'"
                        },
                        "safesearch": {
                            "type": "string",
                            "enum": ["off", "moderate", "strict"],
                            "description": "Safe search level",
                            "default": "moderate"
                        },
                        "country": {
                            "type": "string",
                            "description": "Two-letter country code for results origin (e.g., 'US', 'GB')",
                            "default": "US"
                        }
                    },
                    "required": ["query"]
                }
            }
        }