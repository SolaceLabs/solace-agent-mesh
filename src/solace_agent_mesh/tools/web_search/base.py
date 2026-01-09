"""Base web search tool interface."""

from abc import ABC, abstractmethod
from typing import Literal, Optional
from .models import SearchResult


class WebSearchTool(ABC):
    """Base class for web search tools."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize the search tool.
        
        Args:
            api_key: API key for the search provider (if required)
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self.config = kwargs
    
    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: Literal["basic", "advanced"] = "basic",
        **kwargs
    ) -> SearchResult:
        """Execute a search query.
        
        Args:
            query: The search query string
            max_results: Maximum number of results to return (1-10)
            search_depth: Search depth - 'basic' for quick results, 'advanced' for comprehensive
            **kwargs: Additional provider-specific parameters
            
        Returns:
            SearchResult object containing the search results
            
        Raises:
            Exception: If the search fails
        """
        raise NotImplementedError("Subclasses must implement search()")
    
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
                    "Search the web for current information. Use this when you need "
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
                            "default": 5
                        },
                        "search_depth": {
                            "type": "string",
                            "enum": ["basic", "advanced"],
                            "description": "Search depth: 'basic' for quick results, 'advanced' for comprehensive",
                            "default": "basic"
                        }
                    },
                    "required": ["query"]
                }
            }
        }