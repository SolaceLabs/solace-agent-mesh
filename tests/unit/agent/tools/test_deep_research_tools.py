"""Unit tests for deep research tools helper functions."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from solace_agent_mesh.agent.tools.deep_research_tools import (
    _extract_text_from_llm_response,
    _parse_json_from_llm_response,
    _prepare_findings_summary,
    _prepare_findings_for_report,
    _generate_sources_section,
    _generate_methodology_section,
    SearchResult,
    ReflectionResult,
    ResearchCitationTracker,
)


class TestExtractTextFromLlmResponse:
    """Tests for _extract_text_from_llm_response helper function."""
    
    def test_extract_from_text_attribute(self):
        """Test extraction from response.text attribute."""
        response = MagicMock()
        response.text = "Hello, world!"
        response.parts = None
        response.content = None
        
        result = _extract_text_from_llm_response(response)
        assert result == "Hello, world!"
    
    def test_extract_from_parts_attribute(self):
        """Test extraction from response.parts attribute."""
        part1 = MagicMock()
        part1.text = "Hello, "
        part2 = MagicMock()
        part2.text = "world!"
        
        response = MagicMock()
        response.text = None
        response.parts = [part1, part2]
        response.content = None
        
        result = _extract_text_from_llm_response(response)
        assert result == "Hello, world!"
    
    def test_extract_from_content_parts(self):
        """Test extraction from response.content.parts attribute."""
        part1 = MagicMock()
        part1.text = "Content "
        part2 = MagicMock()
        part2.text = "text"
        
        content = MagicMock()
        content.parts = [part1, part2]
        content.text = None
        
        response = MagicMock()
        response.text = None
        response.parts = None
        response.content = content
        
        result = _extract_text_from_llm_response(response)
        assert result == "Content text"
    
    def test_extract_from_content_text(self):
        """Test extraction from response.content.text attribute."""
        content = MagicMock()
        content.parts = None
        content.text = "Direct content text"
        
        response = MagicMock()
        response.text = None
        response.parts = None
        response.content = content
        
        result = _extract_text_from_llm_response(response)
        assert result == "Direct content text"
    
    def test_extract_from_string_content(self):
        """Test extraction when content is a string."""
        response = MagicMock()
        response.text = None
        response.parts = None
        response.content = "String content"
        
        result = _extract_text_from_llm_response(response)
        assert result == "String content"
    
    def test_extract_empty_response(self):
        """Test extraction from empty response."""
        response = MagicMock()
        response.text = None
        response.parts = None
        response.content = None
        
        result = _extract_text_from_llm_response(response)
        assert result == ""
    
    def test_extract_with_empty_text(self):
        """Test extraction when text is empty string."""
        response = MagicMock()
        response.text = ""
        response.parts = None
        response.content = None
        
        result = _extract_text_from_llm_response(response)
        assert result == ""


class TestParseJsonFromLlmResponse:
    """Tests for _parse_json_from_llm_response helper function."""
    
    def test_parse_valid_json(self):
        """Test parsing valid JSON."""
        response_text = '{"key": "value", "number": 42}'
        result = _parse_json_from_llm_response(response_text)
        assert result == {"key": "value", "number": 42}
    
    def test_parse_json_with_markdown_wrapper(self):
        """Test parsing JSON wrapped in markdown code block."""
        response_text = '```json\n{"key": "value"}\n```'
        result = _parse_json_from_llm_response(response_text)
        assert result == {"key": "value"}
    
    def test_parse_json_with_markdown_no_language(self):
        """Test parsing JSON wrapped in markdown code block without language."""
        response_text = '```\n{"key": "value"}\n```'
        result = _parse_json_from_llm_response(response_text)
        assert result == {"key": "value"}
    
    def test_parse_json_with_whitespace(self):
        """Test parsing JSON with surrounding whitespace."""
        response_text = '  \n  {"key": "value"}  \n  '
        result = _parse_json_from_llm_response(response_text)
        assert result == {"key": "value"}
    
    def test_parse_empty_response(self):
        """Test parsing empty response returns None."""
        result = _parse_json_from_llm_response("")
        assert result is None
    
    def test_parse_whitespace_only_response(self):
        """Test parsing whitespace-only response returns None."""
        result = _parse_json_from_llm_response("   \n\t  ")
        assert result is None
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns None."""
        response_text = "This is not JSON"
        result = _parse_json_from_llm_response(response_text)
        assert result is None
    
    def test_parse_with_fallback_key(self):
        """Test parsing with fallback key extraction."""
        # This tests the regex fallback when direct parsing fails
        response_text = 'Some text before {"queries": ["q1", "q2"]} some text after'
        result = _parse_json_from_llm_response(response_text, fallback_key="queries")
        assert result is not None
        assert "queries" in result
    
    def test_parse_nested_json(self):
        """Test parsing nested JSON structure."""
        response_text = '{"outer": {"inner": "value"}, "list": [1, 2, 3]}'
        result = _parse_json_from_llm_response(response_text)
        assert result == {"outer": {"inner": "value"}, "list": [1, 2, 3]}


class TestSearchResult:
    """Tests for SearchResult dataclass."""
    
    def test_search_result_creation(self):
        """Test creating a SearchResult."""
        result = SearchResult(
            source_type="web",
            title="Test Title",
            content="Test content",
            url="https://example.com",
            relevance_score=0.85
        )
        assert result.source_type == "web"
        assert result.title == "Test Title"
        assert result.content == "Test content"
        assert result.url == "https://example.com"
        assert result.relevance_score == 0.85
        assert result.metadata == {}
        assert result.citation_id is None
    
    def test_search_result_with_metadata(self):
        """Test creating a SearchResult with metadata."""
        result = SearchResult(
            source_type="kb",
            title="KB Result",
            content="Knowledge base content",
            metadata={"provider": "internal"}
        )
        assert result.metadata == {"provider": "internal"}


class TestReflectionResult:
    """Tests for ReflectionResult dataclass."""
    
    def test_reflection_result_creation(self):
        """Test creating a ReflectionResult."""
        result = ReflectionResult(
            quality_score=0.75,
            gaps=["Missing historical context", "Need more sources"],
            should_continue=True,
            suggested_queries=["query1", "query2"],
            reasoning="Good progress but gaps remain"
        )
        assert result.quality_score == 0.75
        assert len(result.gaps) == 2
        assert result.should_continue is True
        assert len(result.suggested_queries) == 2
        assert "Good progress" in result.reasoning


class TestResearchCitationTracker:
    """Tests for ResearchCitationTracker class."""
    
    def test_tracker_initialization(self):
        """Test citation tracker initialization."""
        tracker = ResearchCitationTracker("What is AI?")
        assert tracker.research_question == "What is AI?"
        assert tracker.citations == {}
        assert tracker.citation_counter == 0
        assert tracker.generated_title is None
    
    def test_set_title(self):
        """Test setting research title."""
        tracker = ResearchCitationTracker("What is AI?")
        tracker.set_title("Artificial Intelligence Overview")
        assert tracker.generated_title == "Artificial Intelligence Overview"
    
    def test_start_query(self):
        """Test starting a new query."""
        tracker = ResearchCitationTracker("Research question")
        tracker.start_query("first query")
        assert tracker.current_query == "first query"
        assert tracker.current_query_sources == []
    
    def test_start_query_saves_previous(self):
        """Test that starting a new query saves the previous one."""
        tracker = ResearchCitationTracker("Research question")
        tracker.start_query("first query")
        tracker.start_query("second query")
        
        assert tracker.current_query == "second query"
        assert len(tracker.queries) == 1
        assert tracker.queries[0]["query"] == "first query"
    
    def test_add_citation(self):
        """Test adding a citation."""
        tracker = ResearchCitationTracker("Research question")
        result = SearchResult(
            source_type="web",
            title="Test Source",
            content="Test content",
            url="https://example.com",
            relevance_score=0.9
        )
        
        citation_id = tracker.add_citation(result)
        
        assert citation_id == "search0"
        assert result.citation_id == "search0"
        assert tracker.citation_counter == 1
        assert "search0" in tracker.citations
    
    def test_add_multiple_citations(self):
        """Test adding multiple citations."""
        tracker = ResearchCitationTracker("Research question")
        
        for i in range(3):
            result = SearchResult(
                source_type="web",
                title=f"Source {i}",
                content=f"Content {i}",
                url=f"https://example{i}.com"
            )
            citation_id = tracker.add_citation(result)
            assert citation_id == f"search{i}"
        
        assert tracker.citation_counter == 3
        assert len(tracker.citations) == 3
    
    def test_get_rag_metadata(self):
        """Test getting RAG metadata."""
        tracker = ResearchCitationTracker("What is AI?")
        tracker.set_title("AI Overview")
        
        result = SearchResult(
            source_type="web",
            title="Test Source",
            content="Test content",
            url="https://example.com"
        )
        tracker.add_citation(result)
        
        metadata = tracker.get_rag_metadata()
        
        assert metadata["query"] == "What is AI?"
        assert metadata["searchType"] == "deep_research"
        assert metadata["title"] == "AI Overview"
        assert len(metadata["sources"]) == 1


class TestPrepareFindingsSummary:
    """Tests for _prepare_findings_summary helper function."""
    
    def test_empty_findings(self):
        """Test summary with no findings."""
        result = _prepare_findings_summary([])
        assert result == "No findings yet."
    
    def test_single_finding(self):
        """Test summary with single finding."""
        findings = [
            SearchResult(
                source_type="web",
                title="Test Result",
                content="Test content",
                relevance_score=0.9
            )
        ]
        result = _prepare_findings_summary(findings)
        
        assert "Total Sources: 1" in result
        assert "WEB Sources" in result
        assert "Test Result" in result
    
    def test_multiple_source_types(self):
        """Test summary with multiple source types."""
        findings = [
            SearchResult(source_type="web", title="Web Result", content="Web content", relevance_score=0.9),
            SearchResult(source_type="kb", title="KB Result", content="KB content", relevance_score=0.8),
        ]
        result = _prepare_findings_summary(findings)
        
        assert "Total Sources: 2" in result
        assert "WEB Sources" in result
        assert "KB Sources" in result


class TestPrepareFindingsForReport:
    """Tests for _prepare_findings_for_report helper function."""
    
    def test_empty_findings(self):
        """Test report preparation with no findings."""
        result = _prepare_findings_for_report([])
        assert "# Research Findings" in result
    
    def test_findings_with_fetched_content(self):
        """Test report preparation with fetched content."""
        findings = [
            SearchResult(
                source_type="web",
                title="Fetched Source",
                content="Full content here",
                url="https://example.com",
                relevance_score=0.9,
                metadata={"fetched": True}
            )
        ]
        findings[0].citation_id = "search0"
        
        result = _prepare_findings_for_report(findings)
        
        assert "Detailed Sources" in result
        assert "Fetched Source" in result
        assert "search0" in result
    
    def test_findings_with_snippets_only(self):
        """Test report preparation with snippet-only sources."""
        findings = [
            SearchResult(
                source_type="web",
                title="Snippet Source",
                content="Just a snippet",
                url="https://example.com",
                relevance_score=0.7,
                metadata={"fetched": False}
            )
        ]
        findings[0].citation_id = "search0"
        
        result = _prepare_findings_for_report(findings)
        
        assert "Additional Sources" in result
        assert "Snippet Source" in result


class TestGenerateSourcesSection:
    """Tests for _generate_sources_section helper function."""
    
    def test_empty_sources(self):
        """Test sources section with no sources."""
        result = _generate_sources_section([])
        assert result == ""
    
    def test_web_sources(self):
        """Test sources section with web sources."""
        findings = [
            SearchResult(
                source_type="web",
                title="Web Source 1",
                content="Content",
                url="https://example.com"
            )
        ]
        findings[0].citation_id = "search0"
        
        result = _generate_sources_section(findings)
        
        assert "## References" in result
        assert "Web Source 1" in result
        assert "https://example.com" in result
        assert "[1]" in result  # Citation number should be 1-indexed


class TestGenerateMethodologySection:
    """Tests for _generate_methodology_section helper function."""
    
    def test_methodology_section(self):
        """Test methodology section generation."""
        findings = [
            SearchResult(source_type="web", title="Web 1", content="C1", metadata={"fetched": True}),
            SearchResult(source_type="web", title="Web 2", content="C2", metadata={"fetched": False}),
            SearchResult(source_type="kb", title="KB 1", content="C3", metadata={"fetched": False}),
        ]
        
        result = _generate_methodology_section(findings)
        
        assert "## Research Methodology" in result
        assert "3 sources" in result
        assert "1 sources** were read in full" in result
        assert "2 additional sources" in result
        assert "2 web" in result
        assert "1 knowledge base" in result
