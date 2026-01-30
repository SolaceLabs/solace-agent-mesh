"""Google Custom Search API implementation."""

import httpx
import logging
from typing import Literal, Optional
from urllib.parse import quote
from .base import WebSearchTool
from .models import SearchResult, SearchSource

logger = logging.getLogger(__name__)

# Default number of search results to return
DEFAULT_MAX_RESULTS = 5


class GoogleSearchTool(WebSearchTool):
    """Google Custom Search API implementation."""
    
    def __init__(self, api_key: str, search_engine_id: str, **kwargs):
        """Initialize Google Custom Search tool.
        
        Args:
            api_key: Google API key
            search_engine_id: Google Custom Search Engine ID (CSE ID)
            **kwargs: Additional configuration
        """
        super().__init__(api_key=api_key, **kwargs)
        self.search_engine_id = search_engine_id
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        
        if not self.api_key:
            raise ValueError("Google API key is required")
        if not self.search_engine_id:
            raise ValueError("Google Custom Search Engine ID is required")
    
    async def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        search_depth: Literal["basic", "advanced"] = "basic",
        search_type: Optional[Literal["image"]] = None,
        date_restrict: Optional[str] = None,
        safe_search: Optional[Literal["off", "medium", "high"]] = None,
        **kwargs
    ) -> SearchResult:
        """Execute Google Custom Search.
        
        Args:
            query: Search query string
            max_results: Maximum number of results (1-10)
            search_depth: Not used for Google (kept for interface compatibility)
            search_type: Set to "image" for image search
            date_restrict: Restricts results based on recency (e.g., "d[number]" for days)
            safe_search: Safe search level
            **kwargs: Additional Google CSE parameters
            
        Returns:
            SearchResult object
        """
        try:
            # Ensure max_results is an integer (LLM may pass string)
            try:
                max_results = int(max_results)
            except (TypeError, ValueError):
                max_results = DEFAULT_MAX_RESULTS
            
            # Google CSE allows max 10 results per request
            num_results = min(max(max_results, 1), 10)
            
            # Build query parameters
            params = {
                "key": self.api_key,
                "cx": self.search_engine_id,
                "q": query,
                "num": num_results,
            }
            
            # Add optional parameters
            if search_type:
                params["searchType"] = search_type
            if date_restrict:
                params["dateRestrict"] = date_restrict
            if safe_search:
                params["safe"] = safe_search
            
            # Add any additional kwargs
            params.update(kwargs)
            
            logger.info(f"Executing Google search: query='{query}', num={num_results}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    params=params,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_msg = f"Google API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg += f" - {error_data.get('error', {}).get('message', '')}"
                    except:
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
                items = data.get("items", [])
                
                # Handle image search results separately
                if search_type == "image":
                    from .models import ImageResult
                    for item in items:
                        try:
                            image = ImageResult(
                                imageUrl=item["link"],
                                title=item.get("title", ""),
                                link=item.get("image", {}).get("contextLink", item["link"])
                            )
                            images.append(image)
                        except Exception as e:
                            logger.warning(f"Failed to parse image result: {e}")
                            continue
                else:
                    # Regular web search - add to organic results
                    for item in items:
                        try:
                            # Extract snippet (description)
                            snippet = item.get("snippet", "")
                            
                            # For HTML-formatted snippets, try to get plain text
                            if "htmlSnippet" in item:
                                import html
                                snippet = html.unescape(item["htmlSnippet"])
                                # Remove HTML tags
                                import re
                                snippet = re.sub(r'<[^>]+>', '', snippet)
                            
                            source = SearchSource(
                                link=item["link"],
                                title=item["title"],
                                snippet=snippet,
                                attribution=self._extract_domain(item["link"]),
                                imageUrl=item.get("pagemap", {}).get("cse_thumbnail", [{}])[0].get("src")
                            )
                            organic.append(source)
                        except Exception as e:
                            logger.warning(f"Failed to parse search result: {e}")
                            continue
                
                logger.info(f"Google search successful: {len(organic)} results")
                
                return SearchResult(
                    success=True,
                    query=query,
                    organic=organic,
                    images=images,
                    metadata={
                        "search_engine": "google",
                        "total_results": data.get("searchInformation", {}).get("totalResults"),
                        "search_time": data.get("searchInformation", {}).get("searchTime"),
                    }
                )
                
        except httpx.TimeoutException:
            error_msg = "Google search timed out"
            logger.error(error_msg)
            return SearchResult(
                success=False,
                query=query,
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Google search failed: {str(e)}"
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
        except:
            return url
    
    def get_tool_definition(self) -> dict:
        """Get the tool definition for LLM function calling.
        
        Returns:
            Dictionary containing the tool definition
        """
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the web using Google Custom Search. Use this when you need "
                    "up-to-date information, facts, news, or data that may not be in "
                    "your training data. Always cite sources using the citation format."
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
                            "description": "Maximum number of results (1-10)",
                            "minimum": 1,
                            "maximum": 10,
                            "default": DEFAULT_MAX_RESULTS
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["image"],
                            "description": "Set to 'image' for image search"
                        },
                        "date_restrict": {
                            "type": "string",
                            "description": "Restrict results by recency (e.g., 'd7' for last 7 days)"
                        }
                    },
                    "required": ["query"]
                }
            }
        }