"""Unit tests for Google Custom Search API implementation."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from solace_agent_mesh.tools.web_search.google_search import GoogleSearchTool
from solace_agent_mesh.tools.web_search.models import SearchResult, SearchSource


class TestGoogleSearchToolInit:
    """Tests for GoogleSearchTool initialization."""
    
    def test_init_with_valid_credentials(self):
        """Test successful initialization with valid credentials."""
        tool = GoogleSearchTool(
            api_key="test_api_key",
            search_engine_id="test_cse_id"
        )
        assert tool.api_key == "test_api_key"
        assert tool.search_engine_id == "test_cse_id"
        assert tool.base_url == "https://www.googleapis.com/customsearch/v1"
    
    def test_init_without_api_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        with pytest.raises(ValueError, match="Google API key is required"):
            GoogleSearchTool(api_key="", search_engine_id="test_cse_id")
    
    def test_init_without_cse_id_raises_error(self):
        """Test that missing CSE ID raises ValueError."""
        with pytest.raises(ValueError, match="Google Custom Search Engine ID is required"):
            GoogleSearchTool(api_key="test_api_key", search_engine_id="")
    
    def test_init_with_none_api_key_raises_error(self):
        """Test that None API key raises ValueError."""
        with pytest.raises(ValueError, match="Google API key is required"):
            GoogleSearchTool(api_key=None, search_engine_id="test_cse_id")
    
    def test_init_with_none_cse_id_raises_error(self):
        """Test that None CSE ID raises ValueError."""
        with pytest.raises(ValueError, match="Google Custom Search Engine ID is required"):
            GoogleSearchTool(api_key="test_api_key", search_engine_id=None)


class TestExtractDomain:
    """Tests for the _extract_domain static method."""
    
    def test_extract_domain_https(self):
        """Test domain extraction from HTTPS URL."""
        domain = GoogleSearchTool._extract_domain("https://example.com/path/to/page")
        assert domain == "example.com"
    
    def test_extract_domain_http(self):
        """Test domain extraction from HTTP URL."""
        domain = GoogleSearchTool._extract_domain("http://example.com/path")
        assert domain == "example.com"
    
    def test_extract_domain_with_www(self):
        """Test domain extraction removes www prefix."""
        domain = GoogleSearchTool._extract_domain("https://www.example.com/page")
        assert domain == "example.com"
    
    def test_extract_domain_subdomain(self):
        """Test domain extraction preserves subdomains (except www)."""
        domain = GoogleSearchTool._extract_domain("https://blog.example.com/post")
        assert domain == "blog.example.com"
    
    def test_extract_domain_with_port(self):
        """Test domain extraction with port number."""
        domain = GoogleSearchTool._extract_domain("https://example.com:8080/page")
        assert domain == "example.com:8080"
    
    def test_extract_domain_root_url(self):
        """Test domain extraction from root URL without path."""
        domain = GoogleSearchTool._extract_domain("https://example.com")
        assert domain == "example.com"
    
    def test_extract_domain_root_url_with_trailing_slash(self):
        """Test domain extraction from root URL with trailing slash."""
        domain = GoogleSearchTool._extract_domain("https://example.com/")
        assert domain == "example.com"
    
    def test_extract_domain_complex_url(self):
        """Test domain extraction from complex URL with query params."""
        domain = GoogleSearchTool._extract_domain("https://www.example.com/path?query=value&foo=bar")
        assert domain == "example.com"
    
    def test_extract_domain_invalid_url_returns_original(self):
        """Test that invalid URL returns the original string."""
        # Empty string
        domain = GoogleSearchTool._extract_domain("")
        assert domain == ""
    
    def test_extract_domain_no_protocol(self):
        """Test domain extraction from URL without protocol."""
        domain = GoogleSearchTool._extract_domain("example.com/path")
        assert domain == "example.com"


class TestGoogleSearchToolSearch:
    """Tests for the search method."""
    
    @pytest.fixture
    def google_tool(self):
        """Create a GoogleSearchTool instance for testing."""
        return GoogleSearchTool(
            api_key="test_api_key",
            search_engine_id="test_cse_id"
        )
    
    @pytest.fixture
    def mock_search_response(self):
        """Create a mock successful search response."""
        return {
            "searchInformation": {
                "totalResults": "1000",
                "searchTime": 0.5
            },
            "items": [
                {
                    "title": "Test Result 1",
                    "link": "https://example.com/page1",
                    "snippet": "This is the first test result snippet.",
                    "htmlSnippet": "This is the first test result <b>snippet</b>."
                },
                {
                    "title": "Test Result 2",
                    "link": "https://www.example.org/page2",
                    "snippet": "This is the second test result snippet.",
                    "pagemap": {
                        "cse_thumbnail": [{"src": "https://example.org/thumb.jpg"}]
                    }
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_search_success(self, google_tool, mock_search_response):
        """Test successful search returns results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await google_tool.search("test query", max_results=5)
            
            assert result.success is True
            assert result.query == "test query"
            assert len(result.organic) == 2
            assert result.organic[0].title == "Test Result 1"
            assert result.organic[0].link == "https://example.com/page1"
            assert result.organic[1].title == "Test Result 2"
            assert result.metadata["search_engine"] == "google"
    
    @pytest.mark.asyncio
    async def test_search_max_results_capped_at_10(self, google_tool, mock_search_response):
        """Test that max_results is capped at 10."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(return_value=mock_response)
            
            await google_tool.search("test query", max_results=20)
            
            # Verify the num parameter was capped at 10
            call_args = mock_instance.get.call_args
            assert call_args[1]["params"]["num"] == 10
    
    @pytest.mark.asyncio
    async def test_search_min_results_at_least_1(self, google_tool, mock_search_response):
        """Test that max_results is at least 1."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(return_value=mock_response)
            
            await google_tool.search("test query", max_results=0)
            
            # Verify the num parameter was set to at least 1
            call_args = mock_instance.get.call_args
            assert call_args[1]["params"]["num"] == 1
    
    @pytest.mark.asyncio
    async def test_search_api_error(self, google_tool):
        """Test handling of API error response."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "error": {"message": "API key invalid"}
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await google_tool.search("test query")
            
            assert result.success is False
            assert "403" in result.error
            assert "API key invalid" in result.error
    
    @pytest.mark.asyncio
    async def test_search_timeout(self, google_tool):
        """Test handling of timeout exception."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Connection timed out")
            )
            
            result = await google_tool.search("test query")
            
            assert result.success is False
            assert "timed out" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_search_generic_exception(self, google_tool):
        """Test handling of generic exception."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Network error")
            )
            
            result = await google_tool.search("test query")
            
            assert result.success is False
            assert "Network error" in result.error
    
    @pytest.mark.asyncio
    async def test_search_with_optional_params(self, google_tool, mock_search_response):
        """Test search with optional parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(return_value=mock_response)
            
            await google_tool.search(
                "test query",
                date_restrict="d7",
                safe_search="high"
            )
            
            call_args = mock_instance.get.call_args
            assert call_args[1]["params"]["dateRestrict"] == "d7"
            assert call_args[1]["params"]["safe"] == "high"
    
    @pytest.mark.asyncio
    async def test_search_image_type(self, google_tool):
        """Test image search returns image results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "title": "Test Image",
                    "link": "https://example.com/image.jpg",
                    "image": {"contextLink": "https://example.com/page"}
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await google_tool.search("test image", search_type="image")
            
            assert result.success is True
            assert len(result.images) == 1
            assert result.images[0].imageUrl == "https://example.com/image.jpg"
    
    @pytest.mark.asyncio
    async def test_search_empty_results(self, google_tool):
        """Test handling of empty search results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "searchInformation": {"totalResults": "0"},
            "items": []
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await google_tool.search("obscure query with no results")
            
            assert result.success is True
            assert len(result.organic) == 0
    
    @pytest.mark.asyncio
    async def test_search_malformed_result_item(self, google_tool):
        """Test handling of malformed result items."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"title": "Valid Result", "link": "https://example.com"},
                {"invalid": "item"},  # Missing required fields
                {"title": "Another Valid", "link": "https://example.org"}
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await google_tool.search("test query")
            
            assert result.success is True
            # Should have 2 valid results, skipping the malformed one
            assert len(result.organic) == 2


class TestGetToolDefinition:
    """Tests for the get_tool_definition method."""
    
    def test_get_tool_definition_structure(self):
        """Test that tool definition has correct structure."""
        tool = GoogleSearchTool(
            api_key="test_api_key",
            search_engine_id="test_cse_id"
        )
        
        definition = tool.get_tool_definition()
        
        assert definition["type"] == "function"
        assert "function" in definition
        assert definition["function"]["name"] == "web_search"
        assert "description" in definition["function"]
        assert "parameters" in definition["function"]
    
    def test_get_tool_definition_parameters(self):
        """Test that tool definition has correct parameters."""
        tool = GoogleSearchTool(
            api_key="test_api_key",
            search_engine_id="test_cse_id"
        )
        
        definition = tool.get_tool_definition()
        params = definition["function"]["parameters"]
        
        assert params["type"] == "object"
        assert "query" in params["properties"]
        assert "max_results" in params["properties"]
        assert "search_type" in params["properties"]
        assert "date_restrict" in params["properties"]
        assert params["required"] == ["query"]
