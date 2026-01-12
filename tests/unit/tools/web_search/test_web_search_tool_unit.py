"""Unit tests for web search tools with multi-turn citation support.

These tests cover the citation ID generation and multi-turn search aggregation
functionality in the web_search_tools module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from solace_agent_mesh.agent.tools.web_search_tools import (
    _get_next_search_turn,
    web_search_google,
    _SEARCH_TURN_STATE_KEY,
)


class TestGetNextSearchTurn:
    """Tests for the _get_next_search_turn function."""

    def test_returns_zero_when_no_context(self):
        """Test that function returns 0 when tool_context is None."""
        result = _get_next_search_turn(None)
        assert result == 0

    def test_returns_zero_on_first_call(self):
        """Test that first call returns 0."""
        mock_context = MagicMock()
        mock_context.state = {}
        
        result = _get_next_search_turn(mock_context)
        
        assert result == 0

    def test_increments_state_after_call(self):
        """Test that state is incremented after each call."""
        mock_context = MagicMock()
        mock_context.state = {}
        
        _get_next_search_turn(mock_context)
        
        assert mock_context.state[_SEARCH_TURN_STATE_KEY] == 1

    def test_returns_incremented_values_on_subsequent_calls(self):
        """Test that subsequent calls return incrementing values."""
        mock_context = MagicMock()
        mock_context.state = {}
        
        first = _get_next_search_turn(mock_context)
        second = _get_next_search_turn(mock_context)
        third = _get_next_search_turn(mock_context)
        
        assert first == 0
        assert second == 1
        assert third == 2

    def test_uses_existing_state_value(self):
        """Test that function uses existing state value if present."""
        mock_context = MagicMock()
        mock_context.state = {_SEARCH_TURN_STATE_KEY: 5}
        
        result = _get_next_search_turn(mock_context)
        
        assert result == 5
        assert mock_context.state[_SEARCH_TURN_STATE_KEY] == 6


class TestWebSearchGoogleCitationIds:
    """Tests for citation ID generation in web_search_google."""

    @pytest.fixture
    def mock_tool_config(self):
        """Create mock tool configuration with API keys."""
        return {
            "google_search_api_key": "test_api_key",
            "google_cse_id": "test_cse_id",
        }

    @pytest.fixture
    def mock_search_result(self):
        """Create a mock search result."""
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title

        class MockSearchResult:
            def __init__(self):
                self.success = True
                self.organic = [
                    MockSource("Result 1", "https://example1.com", "Snippet 1"),
                    MockSource("Result 2", "https://example2.com", "Snippet 2"),
                    MockSource("Result 3", "https://example3.com", "Snippet 3"),
                ]
                self.images = []
                self.error = None

            def model_dump_json(self):
                return '{"organic": [], "images": []}'

        return MockSearchResult()

    @pytest.mark.asyncio
    async def test_citation_ids_use_turn_prefix(self, mock_tool_config, mock_search_result):
        """Test that citation IDs include the search turn prefix."""
        mock_context = MagicMock()
        mock_context.state = {}

        with patch(
            "solace_agent_mesh.agent.tools.web_search_tools.GoogleSearchTool"
        ) as MockGoogleTool:
            mock_tool_instance = MockGoogleTool.return_value
            mock_tool_instance.search = AsyncMock(return_value=mock_search_result)

            result = await web_search_google(
                query="test query",
                tool_context=mock_context,
                tool_config=mock_tool_config,
            )

            # First search should use s0r prefix
            assert result["valid_citation_ids"] == ["s0r0", "s0r1", "s0r2"]
            assert result["search_turn"] == 0

    @pytest.mark.asyncio
    async def test_second_search_uses_incremented_turn(
        self, mock_tool_config, mock_search_result
    ):
        """Test that second search uses incremented turn number."""
        mock_context = MagicMock()
        mock_context.state = {}

        with patch(
            "solace_agent_mesh.agent.tools.web_search_tools.GoogleSearchTool"
        ) as MockGoogleTool:
            mock_tool_instance = MockGoogleTool.return_value
            mock_tool_instance.search = AsyncMock(return_value=mock_search_result)

            # First search
            result1 = await web_search_google(
                query="first query",
                tool_context=mock_context,
                tool_config=mock_tool_config,
            )

            # Second search
            result2 = await web_search_google(
                query="second query",
                tool_context=mock_context,
                tool_config=mock_tool_config,
            )

            # First search should use s0r prefix
            assert result1["valid_citation_ids"] == ["s0r0", "s0r1", "s0r2"]
            assert result1["search_turn"] == 0

            # Second search should use s1r prefix
            assert result2["valid_citation_ids"] == ["s1r0", "s1r1", "s1r2"]
            assert result2["search_turn"] == 1

    @pytest.mark.asyncio
    async def test_citation_ids_never_collide_across_searches(
        self, mock_tool_config, mock_search_result
    ):
        """Test that citation IDs from different searches never collide."""
        mock_context = MagicMock()
        mock_context.state = {}

        with patch(
            "solace_agent_mesh.agent.tools.web_search_tools.GoogleSearchTool"
        ) as MockGoogleTool:
            mock_tool_instance = MockGoogleTool.return_value
            mock_tool_instance.search = AsyncMock(return_value=mock_search_result)

            all_citation_ids = []

            # Perform multiple searches
            for i in range(5):
                result = await web_search_google(
                    query=f"query {i}",
                    tool_context=mock_context,
                    tool_config=mock_tool_config,
                )
                all_citation_ids.extend(result["valid_citation_ids"])

            # All citation IDs should be unique
            assert len(all_citation_ids) == len(set(all_citation_ids))

    @pytest.mark.asyncio
    async def test_rag_sources_have_correct_citation_ids(
        self, mock_tool_config, mock_search_result
    ):
        """Test that RAG sources have matching citation IDs."""
        mock_context = MagicMock()
        mock_context.state = {}

        with patch(
            "solace_agent_mesh.agent.tools.web_search_tools.GoogleSearchTool"
        ) as MockGoogleTool:
            mock_tool_instance = MockGoogleTool.return_value
            mock_tool_instance.search = AsyncMock(return_value=mock_search_result)

            result = await web_search_google(
                query="test query",
                tool_context=mock_context,
                tool_config=mock_tool_config,
            )

            rag_metadata = result["rag_metadata"]
            sources = rag_metadata["sources"]

            # Each source should have a citation ID matching the valid_citation_ids
            source_citation_ids = [s["citationId"] for s in sources]
            assert source_citation_ids == result["valid_citation_ids"]

    @pytest.mark.asyncio
    async def test_formatted_results_include_citation_instructions(
        self, mock_tool_config, mock_search_result
    ):
        """Test that formatted results include citation usage instructions."""
        mock_context = MagicMock()
        mock_context.state = {}

        with patch(
            "solace_agent_mesh.agent.tools.web_search_tools.GoogleSearchTool"
        ) as MockGoogleTool:
            mock_tool_instance = MockGoogleTool.return_value
            mock_tool_instance.search = AsyncMock(return_value=mock_search_result)

            result = await web_search_google(
                query="test query",
                tool_context=mock_context,
                tool_config=mock_tool_config,
            )

            formatted = result["formatted_results"]

            # Should include citation IDs in the formatted output
            assert "[[cite:s0r0]]" in formatted
            assert "[[cite:s0r1]]" in formatted
            assert "[[cite:s0r2]]" in formatted

            # Should include instructions about unique citation IDs
            assert "UNIQUE" in formatted
            assert "CITATION ID" in formatted


class TestWebSearchGoogleImageCitations:
    """Tests for image citation ID generation."""

    @pytest.fixture
    def mock_tool_config(self):
        """Create mock tool configuration with API keys."""
        return {
            "google_search_api_key": "test_api_key",
            "google_cse_id": "test_cse_id",
        }

    @pytest.fixture
    def mock_search_result_with_images(self):
        """Create a mock search result with images."""
        class MockSource:
            def __init__(self, title, link, snippet):
                self.title = title
                self.link = link
                self.snippet = snippet
                self.attribution = title

        class MockImage:
            def __init__(self, title, link, imageUrl):
                self.title = title
                self.link = link
                self.imageUrl = imageUrl

        class MockSearchResult:
            def __init__(self):
                self.success = True
                self.organic = [
                    MockSource("Result 1", "https://example1.com", "Snippet 1"),
                ]
                self.images = [
                    MockImage("Image 1", "https://img1.com", "https://img1.com/img.jpg"),
                    MockImage("Image 2", "https://img2.com", "https://img2.com/img.jpg"),
                ]
                self.error = None

            def model_dump_json(self):
                return '{"organic": [], "images": []}'

        return MockSearchResult()

    @pytest.mark.asyncio
    async def test_image_citation_ids_use_turn_prefix(
        self, mock_tool_config, mock_search_result_with_images
    ):
        """Test that image citation IDs include the search turn prefix."""
        mock_context = MagicMock()
        mock_context.state = {}

        with patch(
            "solace_agent_mesh.agent.tools.web_search_tools.GoogleSearchTool"
        ) as MockGoogleTool:
            mock_tool_instance = MockGoogleTool.return_value
            mock_tool_instance.search = AsyncMock(
                return_value=mock_search_result_with_images
            )

            result = await web_search_google(
                query="test query",
                tool_context=mock_context,
                tool_config=mock_tool_config,
            )

            rag_metadata = result["rag_metadata"]
            sources = rag_metadata["sources"]

            # Find image sources
            image_sources = [s for s in sources if s["sourceType"] == "image"]

            # Image citation IDs should use img{turn}r{index} format
            assert len(image_sources) == 2
            assert image_sources[0]["citationId"] == "img0r0"
            assert image_sources[1]["citationId"] == "img0r1"


class TestWebSearchGoogleErrorHandling:
    """Tests for error handling in web_search_google."""

    @pytest.mark.asyncio
    async def test_returns_error_when_config_missing(self):
        """Test that missing config returns error message."""
        result = await web_search_google(
            query="test query",
            tool_context=None,
            tool_config={},
        )

        assert isinstance(result, str)
        assert "Error" in result
        assert "not configured" in result

    @pytest.mark.asyncio
    async def test_returns_error_when_api_key_missing(self):
        """Test that missing API key returns error message."""
        result = await web_search_google(
            query="test query",
            tool_context=None,
            tool_config={"google_cse_id": "test_cse_id"},
        )

        assert isinstance(result, str)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_returns_error_when_search_fails(self):
        """Test that search failure returns error message."""
        mock_context = MagicMock()
        mock_context.state = {}

        class MockFailedResult:
            success = False
            error = "API rate limit exceeded"
            organic = []
            images = []

        with patch(
            "solace_agent_mesh.agent.tools.web_search_tools.GoogleSearchTool"
        ) as MockGoogleTool:
            mock_tool_instance = MockGoogleTool.return_value
            mock_tool_instance.search = AsyncMock(return_value=MockFailedResult())

            result = await web_search_google(
                query="test query",
                tool_context=mock_context,
                tool_config={
                    "google_search_api_key": "test_key",
                    "google_cse_id": "test_cse_id",
                },
            )

            assert isinstance(result, str)
            assert "Error" in result
            assert "API rate limit exceeded" in result
