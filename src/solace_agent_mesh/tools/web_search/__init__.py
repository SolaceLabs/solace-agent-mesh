"""Web search tools for Solace Agent Mesh.

This module provides Google Search integration. For other search providers
(Exa, Brave, Tavily), please use the corresponding plugins from
solace-agent-mesh-plugins repository.
"""

from .models import SearchSource, SearchResult, ImageResult
from .base import WebSearchTool
from .google_search import GoogleSearchTool

__all__ = [
    "SearchSource",
    "SearchResult",
    "ImageResult",
    "WebSearchTool",
    "GoogleSearchTool",
]