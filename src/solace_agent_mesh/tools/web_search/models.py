"""Data models for web search results."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class SearchSource(BaseModel):
    """Individual search result source."""
    
    link: str = Field(..., description="URL of the source")
    title: str = Field(..., description="Title of the source")
    snippet: str = Field(..., description="Text snippet from the source")
    attribution: Optional[str] = Field(None, description="Attribution/domain name")
    imageUrl: Optional[str] = Field(None, description="Optional image URL")
    processed: bool = Field(default=False, description="Whether source has been cited")
    
    class Config:
        json_schema_extra = {
            "example": {
                "link": "https://example.com/article",
                "title": "Example Article",
                "snippet": "This is an example snippet from the article...",
                "attribution": "example.com",
                "processed": False
            }
        }


class ImageResult(BaseModel):
    """Image search result."""
    
    imageUrl: str = Field(..., description="URL of the image")
    title: Optional[str] = Field(None, description="Title or description of the image")
    link: str = Field(..., description="Source page URL")
    
    class Config:
        json_schema_extra = {
            "example": {
                "imageUrl": "https://example.com/image.jpg",
                "title": "Example Image",
                "link": "https://example.com/page"
            }
        }


class SearchResult(BaseModel):
    """Complete search result from a search provider."""
    
    success: bool = Field(..., description="Whether the search was successful")
    query: str = Field(..., description="The search query")
    organic: List[SearchSource] = Field(default_factory=list, description="Organic search results")
    topStories: List[SearchSource] = Field(default_factory=list, description="Top news stories")
    images: List[ImageResult] = Field(default_factory=list, description="Image results")
    answerBox: Optional[str] = Field(None, description="Direct answer if available")
    error: Optional[str] = Field(None, description="Error message if search failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "query": "latest AI developments",
                "organic": [
                    {
                        "link": "https://example.com/ai-news",
                        "title": "Latest AI Developments",
                        "snippet": "Recent advances in artificial intelligence...",
                        "attribution": "example.com"
                    }
                ],
                "topStories": [],
                "images": [],
                "answerBox": None,
                "error": None
            }
        }


class SearchResultData(BaseModel):
    """Search result data with turn information for citations."""
    
    turn: int = Field(..., description="Search turn number (0-based)")
    organic: List[SearchSource] = Field(default_factory=list)
    topStories: List[SearchSource] = Field(default_factory=list)
    images: List[ImageResult] = Field(default_factory=list)
    references: List[Dict[str, Any]] = Field(default_factory=list, description="Additional references")
    answerBox: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "turn": 0,
                "organic": [],
                "topStories": [],
                "images": [],
                "references": [],
                "answerBox": None
            }
        }