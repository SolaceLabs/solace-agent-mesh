"""Tavily search tool implementation."""

import httpx
import logging
from typing import Literal, Optional, List
from .base import WebSearchTool
from .models import SearchResult, SearchSource, ImageResult

logger = logging.getLogger(__name__)


class TavilySearchTool(WebSearchTool):
    """Tavily search API implementation."""
    
    def __init__(self, api_key: str, **kwargs):
        """Initialize Tavily search tool.
        
        Args:
            api_key: Tavily API key
            **kwargs: Additional configuration
        """
        super().__init__(api_key=api_key, **kwargs)
        self.base_url = "https://api.tavily.com/search"
        
        if not self.api_key:
            raise ValueError("Tavily API key is required")
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: Literal["basic", "advanced"] = "basic",
        include_images: bool = False,
        include_answer: bool = False,
        topic: Optional[Literal["general", "news", "finance"]] = None,
        time_range: Optional[Literal["day", "week", "month", "year", "d", "w", "m", "y"]] = None,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        **kwargs
    ) -> SearchResult:
        """Execute Tavily search.
        
        Args:
            query: Search query string
            max_results: Maximum number of results (1-10)
            search_depth: 'basic' for quick results, 'advanced' for comprehensive
            include_images: Whether to include image results
            include_answer: Whether to include direct answer
            topic: Search topic category
            time_range: Time range for results
            include_domains: List of domains to include
            exclude_domains: List of domains to exclude
            **kwargs: Additional parameters
            
        Returns:
            SearchResult object
        """
        try:
            payload = {
                "api_key": self.api_key,
                "query": query,
                "max_results": min(max(max_results, 1), 10),
                "search_depth": search_depth,
                "include_images": include_images,
                "include_answer": include_answer,
            }
            
            # Add optional parameters
            if topic:
                payload["topic"] = topic
            if time_range:
                payload["time_range"] = time_range
            if include_domains:
                payload["include_domains"] = include_domains
            if exclude_domains:
                payload["exclude_domains"] = exclude_domains
            
            # Add any additional kwargs
            payload.update(kwargs)
            
            logger.info(f"Executing Tavily search: query='{query}', depth={search_depth}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_msg = f"Tavily API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg += f" - {error_data.get('detail', {}).get('error', error_data.get('error', ''))}"
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
                for result in data.get("results", []):
                    try:
                        source = SearchSource(
                            link=result["url"],
                            title=result["title"],
                            snippet=result["content"],
                            attribution=self._extract_domain(result["url"])
                        )
                        organic.append(source)
                    except Exception as e:
                        logger.warning(f"Failed to parse search result: {e}")
                        continue
                
                # Parse images if included
                images = []
                if include_images and "images" in data:
                    for img in data["images"]:
                        try:
                            image = ImageResult(
                                imageUrl=img.get("url", img.get("imageUrl", "")),
                                title=img.get("title", img.get("description")),
                                link=img.get("url", img.get("imageUrl", ""))
                            )
                            images.append(image)
                        except Exception as e:
                            logger.warning(f"Failed to parse image result: {e}")
                            continue
                
                logger.info(f"Tavily search successful: {len(organic)} results")
                
                return SearchResult(
                    success=True,
                    query=query,
                    organic=organic,
                    images=images,
                    answerBox=data.get("answer"),
                    metadata={
                        "search_depth": search_depth,
                        "response_time": data.get("response_time"),
                    }
                )
                
        except httpx.TimeoutException:
            error_msg = "Tavily search timed out"
            logger.error(error_msg)
            return SearchResult(
                success=False,
                query=query,
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Tavily search failed: {str(e)}"
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