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
    _get_model_for_phase,
    _send_research_progress,
    _send_rag_info_update,
    _send_deep_research_report_signal,
    _generate_initial_queries,
    _generate_research_title,
    _reflect_on_findings,
    _select_sources_to_fetch,
    _search_web,
    _multi_source_search,
    _fetch_selected_sources,
    _generate_research_report,
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
        
        assert citation_id == "research0"
        assert result.citation_id == "research0"
        assert tracker.citation_counter == 1
        assert "research0" in tracker.citations
    
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
            assert citation_id == f"research{i}"
        
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
        findings[0].citation_id = "research0"
        
        result = _prepare_findings_for_report(findings)
        
        assert "Detailed Sources" in result
        assert "Fetched Source" in result
        assert "research0" in result
    
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
        findings[0].citation_id = "research0"
        
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
        findings[0].citation_id = "research0"
        
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


class TestGetModelForPhase:
    """Tests for _get_model_for_phase helper function."""
    
    def _create_mock_tool_context(self, agent=None, canonical_model=None, host_component=None):
        """Helper to create a mock tool context with configurable agent and model."""
        mock_context = MagicMock()
        mock_inv_context = MagicMock()
        
        if agent is None:
            agent = MagicMock()
            agent.canonical_model = canonical_model
            agent.host_component = host_component
        
        mock_inv_context.agent = agent
        mock_context._invocation_context = mock_inv_context
        
        return mock_context
    
    def test_returns_canonical_model_when_available(self):
        """Test that canonical_model is returned when available."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        result = _get_model_for_phase("query_generation", tool_context, None)
        
        assert result == mock_model
    
    def test_fallback_to_host_component_string_model(self):
        """Test fallback to host_component model config when canonical_model is None (string config)."""
        mock_host_component = MagicMock()
        mock_host_component.get_config.return_value = "gpt-4-turbo"
        
        mock_agent = MagicMock()
        mock_agent.canonical_model = None
        mock_agent.host_component = mock_host_component
        
        tool_context = self._create_mock_tool_context(agent=mock_agent)
        
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm') as mock_lite_llm:
            mock_lite_llm.return_value = MagicMock()
            result = _get_model_for_phase("query_generation", tool_context, None)
            
            mock_lite_llm.assert_called_once_with(model="gpt-4-turbo")
    
    def test_fallback_to_host_component_dict_model(self):
        """Test fallback to host_component model config when canonical_model is None (dict config)."""
        mock_host_component = MagicMock()
        mock_host_component.get_config.return_value = {"model": "gpt-4-turbo", "temperature": 0.5}
        
        mock_agent = MagicMock()
        mock_agent.canonical_model = None
        mock_agent.host_component = mock_host_component
        
        tool_context = self._create_mock_tool_context(agent=mock_agent)
        
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm') as mock_lite_llm:
            mock_lite_llm.return_value = MagicMock()
            result = _get_model_for_phase("query_generation", tool_context, None)
            
            mock_lite_llm.assert_called_once_with(model="gpt-4-turbo", temperature=0.5)
    
    def test_raises_value_error_when_no_model_available(self):
        """Test that ValueError is raised when no default model is available."""
        mock_agent = MagicMock()
        mock_agent.canonical_model = None
        mock_agent.host_component = None
        
        tool_context = self._create_mock_tool_context(agent=mock_agent)
        
        with pytest.raises(ValueError, match="No default model available"):
            _get_model_for_phase("query_generation", tool_context, None)
    
    def test_raises_value_error_when_no_agent(self):
        """Test that ValueError is raised when no agent is available."""
        mock_context = MagicMock()
        mock_inv_context = MagicMock()
        mock_inv_context.agent = None
        mock_context._invocation_context = mock_inv_context
        
        with pytest.raises(ValueError, match="No default model available"):
            _get_model_for_phase("query_generation", mock_context, None)
    
    def test_returns_default_model_when_no_tool_config(self):
        """Test that default model is returned when tool_config is None."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        result = _get_model_for_phase("query_generation", tool_context, None)
        
        assert result == mock_model
    
    def test_uses_phase_specific_model_from_models_config(self):
        """Test using phase-specific model from 'models' config (simple string)."""
        mock_default_model = MagicMock()
        mock_default_model.model = "gpt-4"
        mock_default_model._additional_args = {"api_key": "test-key", "api_base": "https://api.example.com"}
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_default_model)
        
        tool_config = {
            "models": {
                "query_generation": "gpt-4o-mini"
            }
        }
        
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm') as mock_lite_llm:
            mock_lite_llm.return_value = MagicMock()
            result = _get_model_for_phase("query_generation", tool_context, tool_config)
            
            # Should be called with the phase-specific model and inherited base config
            mock_lite_llm.assert_called_once()
            call_kwargs = mock_lite_llm.call_args[1]
            assert call_kwargs.get("model") == "gpt-4o-mini"
            assert call_kwargs.get("api_key") == "test-key"
            assert call_kwargs.get("api_base") == "https://api.example.com"
    
    def test_uses_phase_specific_model_from_model_configs(self):
        """Test using phase-specific model from 'model_configs' config (full dict)."""
        mock_default_model = MagicMock()
        mock_default_model.model = "gpt-4"
        mock_default_model._additional_args = {"api_key": "test-key"}
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_default_model)
        
        tool_config = {
            "model_configs": {
                "report_generation": {
                    "model": "claude-3-5-sonnet",
                    "temperature": 0.7,
                    "max_tokens": 16000
                }
            }
        }
        
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm') as mock_lite_llm:
            mock_lite_llm.return_value = MagicMock()
            result = _get_model_for_phase("report_generation", tool_context, tool_config)
            
            mock_lite_llm.assert_called_once()
            call_kwargs = mock_lite_llm.call_args[1]
            assert call_kwargs.get("model") == "claude-3-5-sonnet"
            assert call_kwargs.get("temperature") == 0.7
            assert call_kwargs.get("max_tokens") == 16000
            assert call_kwargs.get("api_key") == "test-key"
    
    def test_model_configs_removes_max_completion_tokens_conflict(self):
        """Test that max_completion_tokens is removed when max_tokens is specified."""
        mock_default_model = MagicMock()
        mock_default_model.model = "gpt-4"
        mock_default_model._additional_args = {"api_key": "test-key", "max_completion_tokens": 4096}
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_default_model)
        
        tool_config = {
            "model_configs": {
                "report_generation": {
                    "model": "claude-3-5-sonnet",
                    "max_tokens": 16000
                }
            }
        }
        
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm') as mock_lite_llm:
            mock_lite_llm.return_value = MagicMock()
            result = _get_model_for_phase("report_generation", tool_context, tool_config)
            
            mock_lite_llm.assert_called_once()
            call_kwargs = mock_lite_llm.call_args[1]
            # max_completion_tokens should be removed to avoid conflict
            assert "max_completion_tokens" not in call_kwargs
            assert call_kwargs.get("max_tokens") == 16000
    
    def test_fallback_to_default_when_phase_not_in_config(self):
        """Test fallback to default model when phase is not in config."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        mock_model._additional_args = {}
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        tool_config = {
            "models": {
                "query_generation": "gpt-4o-mini"  # Different phase
            }
        }
        
        result = _get_model_for_phase("report_generation", tool_context, tool_config)
        
        # Should return the default model since report_generation is not configured
        assert result == mock_model
    
    def test_base_config_excludes_model_specific_params(self):
        """Test that base config excludes model-specific parameters."""
        mock_default_model = MagicMock()
        mock_default_model.model = "gpt-4"
        mock_default_model._additional_args = {
            "api_key": "test-key",
            "api_base": "https://api.example.com",
            "model": "should-be-excluded",
            "messages": "should-be-excluded",
            "tools": "should-be-excluded",
            "stream": True,
            "temperature": 0.5,
            "max_tokens": 1000,
            "max_output_tokens": 2000,
            "max_completion_tokens": 3000,
            "top_p": 0.9,
            "top_k": 40,
            "custom_param": "should-be-included"
        }
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_default_model)
        
        tool_config = {
            "models": {
                "query_generation": "gpt-4o-mini"
            }
        }
        
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm') as mock_lite_llm:
            mock_lite_llm.return_value = MagicMock()
            result = _get_model_for_phase("query_generation", tool_context, tool_config)
            
            mock_lite_llm.assert_called_once()
            call_kwargs = mock_lite_llm.call_args[1]
            
            # Should include api_key, api_base, and custom_param
            assert call_kwargs.get("api_key") == "test-key"
            assert call_kwargs.get("api_base") == "https://api.example.com"
            assert call_kwargs.get("custom_param") == "should-be-included"
            
            # Should exclude model-specific params
            assert "messages" not in call_kwargs or call_kwargs.get("messages") != "should-be-excluded"
            assert "tools" not in call_kwargs or call_kwargs.get("tools") != "should-be-excluded"
            assert "stream" not in call_kwargs
            assert "temperature" not in call_kwargs
            assert "max_tokens" not in call_kwargs
            assert "max_output_tokens" not in call_kwargs
            assert "max_completion_tokens" not in call_kwargs
            assert "top_p" not in call_kwargs
            assert "top_k" not in call_kwargs
    
    def test_no_additional_args_on_default_model(self):
        """Test handling when default model has no _additional_args."""
        mock_default_model = MagicMock()
        mock_default_model.model = "gpt-4"
        # No _additional_args attribute
        del mock_default_model._additional_args
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_default_model)
        
        tool_config = {
            "models": {
                "query_generation": "gpt-4o-mini"
            }
        }
        
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm') as mock_lite_llm:
            mock_lite_llm.return_value = MagicMock()
            result = _get_model_for_phase("query_generation", tool_context, tool_config)
            
            # Should still work, just without inherited config
            mock_lite_llm.assert_called_once_with(model="gpt-4o-mini")
    
    def test_empty_additional_args_on_default_model(self):
        """Test handling when default model has empty _additional_args."""
        mock_default_model = MagicMock()
        mock_default_model.model = "gpt-4"
        mock_default_model._additional_args = {}
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_default_model)
        
        tool_config = {
            "models": {
                "query_generation": "gpt-4o-mini"
            }
        }
        
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm') as mock_lite_llm:
            mock_lite_llm.return_value = MagicMock()
            result = _get_model_for_phase("query_generation", tool_context, tool_config)
            
            # Should still work with empty base config
            mock_lite_llm.assert_called_once_with(model="gpt-4o-mini")


@pytest.mark.asyncio
class TestSendResearchProgress:
    """Tests for _send_research_progress async helper function."""
    
    def _create_mock_tool_context(self, a2a_context=None, invocation_context=None, agent=None, host_component=None):
        """Helper to create a mock tool context."""
        mock_context = MagicMock()
        mock_context.state = MagicMock()
        mock_context.state.get = MagicMock(return_value=a2a_context)
        
        if invocation_context is None:
            invocation_context = MagicMock()
            if agent is None:
                agent = MagicMock()
                agent.host_component = host_component
            invocation_context.agent = agent
        
        mock_context._invocation_context = invocation_context
        
        return mock_context
    
    async def test_returns_early_when_no_a2a_context(self):
        """Test that function returns early when no a2a_context is found."""
        tool_context = self._create_mock_tool_context(a2a_context=None)
        
        # Should not raise, just return early
        await _send_research_progress("Test message", tool_context)
        
        # Verify state.get was called
        tool_context.state.get.assert_called_once_with("a2a_context")
    
    async def test_returns_early_when_no_invocation_context(self):
        """Test that function returns early when no invocation context is found."""
        mock_context = MagicMock()
        mock_context.state = MagicMock()
        mock_context.state.get = MagicMock(return_value={"task_id": "test"})
        mock_context._invocation_context = None
        
        # Should not raise, just return early
        await _send_research_progress("Test message", mock_context)
    
    async def test_returns_early_when_no_agent(self):
        """Test that function returns early when no agent is found."""
        mock_inv_context = MagicMock()
        mock_inv_context.agent = None
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            invocation_context=mock_inv_context
        )
        
        # Should not raise, just return early
        await _send_research_progress("Test message", tool_context)
    
    async def test_returns_early_when_no_host_component(self):
        """Test that function returns early when no host component is found."""
        mock_agent = MagicMock()
        mock_agent.host_component = None
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            agent=mock_agent
        )
        
        # Should not raise, just return early
        await _send_research_progress("Test message", tool_context)
    
    async def test_sends_structured_progress_when_phase_provided(self):
        """Test that structured DeepResearchProgressData is sent when phase is provided."""
        mock_host_component = MagicMock()
        mock_agent = MagicMock()
        mock_agent.host_component = mock_host_component
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            agent=mock_agent,
            host_component=mock_host_component
        )
        
        with patch('solace_agent_mesh.common.data_parts.DeepResearchProgressData') as mock_progress_data:
            mock_progress_data.return_value = MagicMock()
            
            await _send_research_progress(
                "Searching...",
                tool_context,
                phase="searching",
                progress_percentage=50,
                current_iteration=2,
                total_iterations=5,
                sources_found=10,
                current_query="test query",
                fetching_urls=[{"url": "https://example.com"}],
                elapsed_seconds=30,
                max_runtime_seconds=300
            )
            
            # Verify DeepResearchProgressData was created with correct params
            mock_progress_data.assert_called_once()
            call_kwargs = mock_progress_data.call_args[1]
            assert call_kwargs["phase"] == "searching"
            assert call_kwargs["status_text"] == "Searching..."
            assert call_kwargs["progress_percentage"] == 50
            assert call_kwargs["current_iteration"] == 2
            assert call_kwargs["total_iterations"] == 5
            assert call_kwargs["sources_found"] == 10
            assert call_kwargs["current_query"] == "test query"
            assert call_kwargs["elapsed_seconds"] == 30
            assert call_kwargs["max_runtime_seconds"] == 300
    
    async def test_sends_simple_progress_when_no_phase(self):
        """Test that simple AgentProgressUpdateData is sent when no phase is provided."""
        mock_host_component = MagicMock()
        mock_agent = MagicMock()
        mock_agent.host_component = mock_host_component
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            agent=mock_agent,
            host_component=mock_host_component
        )
        
        with patch('solace_agent_mesh.common.data_parts.AgentProgressUpdateData') as mock_progress_data:
            mock_progress_data.return_value = MagicMock()
            
            await _send_research_progress("Simple message", tool_context)
            
            # Verify AgentProgressUpdateData was created
            mock_progress_data.assert_called_once_with(status_text="Simple message")
    
    async def test_handles_exception_gracefully(self):
        """Test that exceptions are caught and logged."""
        mock_host_component = MagicMock()
        mock_host_component.publish_data_signal_from_thread.side_effect = Exception("Test error")
        mock_agent = MagicMock()
        mock_agent.host_component = mock_host_component
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            agent=mock_agent,
            host_component=mock_host_component
        )
        
        # Should not raise, just log the error
        await _send_research_progress("Test message", tool_context, phase="searching")


@pytest.mark.asyncio
class TestSendRagInfoUpdate:
    """Tests for _send_rag_info_update async helper function."""
    
    def _create_mock_tool_context(self, a2a_context=None, invocation_context=None, agent=None, host_component=None):
        """Helper to create a mock tool context."""
        mock_context = MagicMock()
        mock_context.state = MagicMock()
        mock_context.state.get = MagicMock(return_value=a2a_context)
        
        if invocation_context is None:
            invocation_context = MagicMock()
            if agent is None:
                agent = MagicMock()
                agent.host_component = host_component
            invocation_context.agent = agent
        
        mock_context._invocation_context = invocation_context
        
        return mock_context
    
    async def test_returns_early_when_no_a2a_context(self):
        """Test that function returns early when no a2a_context is found."""
        tool_context = self._create_mock_tool_context(a2a_context=None)
        tracker = ResearchCitationTracker("Test question")
        
        # Should not raise, just return early
        await _send_rag_info_update(tracker, tool_context)
        
        # Verify state.get was called
        tool_context.state.get.assert_called_once_with("a2a_context")
    
    async def test_returns_early_when_no_invocation_context(self):
        """Test that function returns early when no invocation context is found."""
        mock_context = MagicMock()
        mock_context.state = MagicMock()
        mock_context.state.get = MagicMock(return_value={"task_id": "test"})
        mock_context._invocation_context = None
        
        tracker = ResearchCitationTracker("Test question")
        
        # Should not raise, just return early
        await _send_rag_info_update(tracker, mock_context)
    
    async def test_returns_early_when_no_agent(self):
        """Test that function returns early when no agent is found."""
        mock_inv_context = MagicMock()
        mock_inv_context.agent = None
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            invocation_context=mock_inv_context
        )
        
        tracker = ResearchCitationTracker("Test question")
        
        # Should not raise, just return early
        await _send_rag_info_update(tracker, tool_context)
    
    async def test_returns_early_when_no_host_component(self):
        """Test that function returns early when no host component is found."""
        mock_agent = MagicMock()
        mock_agent.host_component = None
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            agent=mock_agent
        )
        
        tracker = ResearchCitationTracker("Test question")
        
        # Should not raise, just return early
        await _send_rag_info_update(tracker, tool_context)
    
    async def test_sends_rag_info_with_generated_title(self):
        """Test that RAG info is sent with generated title."""
        mock_host_component = MagicMock()
        mock_agent = MagicMock()
        mock_agent.host_component = mock_host_component
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            agent=mock_agent,
            host_component=mock_host_component
        )
        
        tracker = ResearchCitationTracker("What is AI?")
        tracker.set_title("Artificial Intelligence Overview")
        
        with patch('solace_agent_mesh.common.data_parts.RAGInfoUpdateData') as mock_rag_data:
            mock_rag_data.return_value = MagicMock()
            
            await _send_rag_info_update(tracker, tool_context, is_complete=True)
            
            # Verify RAGInfoUpdateData was created with correct params
            mock_rag_data.assert_called_once()
            call_kwargs = mock_rag_data.call_args[1]
            assert call_kwargs["title"] == "Artificial Intelligence Overview"
            assert call_kwargs["query"] == "What is AI?"
            assert call_kwargs["search_type"] == "deep_research"
            assert call_kwargs["is_complete"] is True
    
    async def test_uses_research_question_as_fallback_title(self):
        """Test that research question is used as fallback when no title is set."""
        mock_host_component = MagicMock()
        mock_agent = MagicMock()
        mock_agent.host_component = mock_host_component
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            agent=mock_agent,
            host_component=mock_host_component
        )
        
        tracker = ResearchCitationTracker("What is machine learning?")
        # Don't set a title
        
        with patch('solace_agent_mesh.common.data_parts.RAGInfoUpdateData') as mock_rag_data:
            mock_rag_data.return_value = MagicMock()
            
            await _send_rag_info_update(tracker, tool_context, is_complete=False)
            
            # Verify title falls back to research question
            call_kwargs = mock_rag_data.call_args[1]
            assert call_kwargs["title"] == "What is machine learning?"
    
    async def test_includes_sources_from_tracker(self):
        """Test that sources from citation tracker are included."""
        mock_host_component = MagicMock()
        mock_agent = MagicMock()
        mock_agent.host_component = mock_host_component
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            agent=mock_agent,
            host_component=mock_host_component
        )
        
        tracker = ResearchCitationTracker("Test question")
        # Add some citations
        result1 = SearchResult(source_type="web", title="Source 1", content="Content 1", url="https://example1.com")
        result2 = SearchResult(source_type="web", title="Source 2", content="Content 2", url="https://example2.com")
        tracker.add_citation(result1)
        tracker.add_citation(result2)
        
        with patch('solace_agent_mesh.common.data_parts.RAGInfoUpdateData') as mock_rag_data:
            mock_rag_data.return_value = MagicMock()
            
            await _send_rag_info_update(tracker, tool_context)
            
            # Verify sources are included
            call_kwargs = mock_rag_data.call_args[1]
            assert len(call_kwargs["sources"]) == 2
    
    async def test_handles_exception_gracefully(self):
        """Test that exceptions are caught and logged."""
        mock_host_component = MagicMock()
        mock_host_component.publish_data_signal_from_thread.side_effect = Exception("Test error")
        mock_agent = MagicMock()
        mock_agent.host_component = mock_host_component
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            agent=mock_agent,
            host_component=mock_host_component
        )
        
        tracker = ResearchCitationTracker("Test question")
        
        # Should not raise, just log the error
        await _send_rag_info_update(tracker, tool_context)


@pytest.mark.asyncio
class TestGenerateInitialQueries:
    """Tests for _generate_initial_queries async function."""
    
    def _create_mock_tool_context(self, canonical_model=None):
        """Helper to create a mock tool context with a model."""
        mock_context = MagicMock()
        mock_inv_context = MagicMock()
        mock_agent = MagicMock()
        mock_agent.canonical_model = canonical_model
        mock_agent.host_component = None
        mock_inv_context.agent = mock_agent
        mock_context._invocation_context = mock_inv_context
        return mock_context
    
    async def test_returns_queries_from_llm_response(self):
        """Test that queries are extracted from LLM JSON response."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with queries
        mock_response = MagicMock()
        mock_response.text = '{"queries": ["query1", "query2", "query3"]}'
        mock_response.parts = None
        mock_response.content = None
        
        # Make generate_content_async return an async generator
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        result = await _generate_initial_queries("What is AI?", tool_context, None)
        
        assert len(result) == 3
        assert "query1" in result
        assert "query2" in result
        assert "query3" in result
    
    async def test_returns_fallback_on_empty_response(self):
        """Test that research question is returned as fallback on empty response."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with empty text
        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        result = await _generate_initial_queries("What is AI?", tool_context, None)
        
        assert result == ["What is AI?"]
    
    async def test_returns_fallback_on_invalid_json(self):
        """Test that research question is returned as fallback on invalid JSON."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with invalid JSON
        mock_response = MagicMock()
        mock_response.text = "This is not valid JSON"
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        result = await _generate_initial_queries("What is AI?", tool_context, None)
        
        assert result == ["What is AI?"]
    
    async def test_returns_fallback_on_exception(self):
        """Test that research question is returned as fallback on exception."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Make generate_content_async raise an exception
        mock_model.generate_content_async = MagicMock(side_effect=Exception("LLM error"))
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        result = await _generate_initial_queries("What is AI?", tool_context, None)
        
        assert result == ["What is AI?"]
    
    async def test_limits_queries_to_five(self):
        """Test that queries are limited to 5."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with more than 5 queries
        mock_response = MagicMock()
        mock_response.text = '{"queries": ["q1", "q2", "q3", "q4", "q5", "q6", "q7"]}'
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        result = await _generate_initial_queries("What is AI?", tool_context, None)
        
        assert len(result) == 5


@pytest.mark.asyncio
class TestGenerateResearchTitle:
    """Tests for _generate_research_title async function."""
    
    def _create_mock_tool_context(self, canonical_model=None):
        """Helper to create a mock tool context with a model."""
        mock_context = MagicMock()
        mock_inv_context = MagicMock()
        mock_agent = MagicMock()
        mock_agent.canonical_model = canonical_model
        mock_agent.host_component = None
        mock_inv_context.agent = mock_agent
        mock_context._invocation_context = mock_inv_context
        return mock_context
    
    async def test_returns_title_from_llm_response(self):
        """Test that title is extracted from LLM response."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with title
        mock_response = MagicMock()
        mock_response.text = "Artificial Intelligence Overview"
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        result = await _generate_research_title("What is artificial intelligence?", tool_context, None)
        
        assert result == "Artificial Intelligence Overview"
    
    async def test_strips_quotes_from_title(self):
        """Test that quotes are stripped from title."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with quoted title
        mock_response = MagicMock()
        mock_response.text = '"AI Overview"'
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        result = await _generate_research_title("What is AI?", tool_context, None)
        
        assert result == "AI Overview"
    
    async def test_returns_truncated_question_on_empty_response(self):
        """Test that truncated question is returned on empty response."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with empty text
        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        result = await _generate_research_title("What is AI?", tool_context, None)
        
        assert result == "What is AI?"
    
    async def test_returns_truncated_question_on_exception(self):
        """Test that truncated question is returned on exception."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Make generate_content_async raise an exception
        mock_model.generate_content_async = MagicMock(side_effect=Exception("LLM error"))
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        result = await _generate_research_title("What is AI?", tool_context, None)
        
        assert result == "What is AI?"
    
    async def test_truncates_long_questions(self):
        """Test that long questions are truncated."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Make generate_content_async raise an exception to trigger fallback
        mock_model.generate_content_async = MagicMock(side_effect=Exception("LLM error"))
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        long_question = "A" * 100  # 100 character question
        result = await _generate_research_title(long_question, tool_context, None)
        
        assert len(result) == 63  # 60 chars + "..."
        assert result.endswith("...")


@pytest.mark.asyncio
class TestReflectOnFindings:
    """Tests for _reflect_on_findings async function."""
    
    def _create_mock_tool_context(self, canonical_model=None):
        """Helper to create a mock tool context with a model."""
        mock_context = MagicMock()
        mock_inv_context = MagicMock()
        mock_agent = MagicMock()
        mock_agent.canonical_model = canonical_model
        mock_agent.host_component = None
        mock_inv_context.agent = mock_agent
        mock_context._invocation_context = mock_inv_context
        return mock_context
    
    async def test_returns_reflection_result_from_llm(self):
        """Test that ReflectionResult is created from LLM response."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with reflection data
        mock_response = MagicMock()
        mock_response.text = '''{
            "quality_score": 0.75,
            "gaps": ["Missing historical context"],
            "should_continue": true,
            "suggested_queries": ["AI history", "AI applications"],
            "reasoning": "Good progress but gaps remain"
        }'''
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        findings = [
            SearchResult(source_type="web", title="Source 1", content="Content 1", relevance_score=0.9)
        ]
        
        result = await _reflect_on_findings("What is AI?", findings, 1, tool_context, 10, None)
        
        assert isinstance(result, ReflectionResult)
        assert result.quality_score == 0.75
        assert "Missing historical context" in result.gaps
        assert result.should_continue is True
        assert len(result.suggested_queries) == 2
    
    async def test_returns_fallback_on_empty_response(self):
        """Test that fallback ReflectionResult is returned on empty response."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with empty text
        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        findings = [
            SearchResult(source_type="web", title="Source 1", content="Content 1", relevance_score=0.9)
        ]
        
        result = await _reflect_on_findings("What is AI?", findings, 1, tool_context, 10, None)
        
        assert isinstance(result, ReflectionResult)
        assert result.quality_score == 0.6
        assert "Need more sources" in result.gaps
    
    async def test_returns_fallback_on_exception(self):
        """Test that fallback ReflectionResult is returned on exception."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Make generate_content_async raise an exception
        mock_model.generate_content_async = MagicMock(side_effect=Exception("LLM error"))
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        findings = [
            SearchResult(source_type="web", title="Source 1", content="Content 1", relevance_score=0.9)
        ]
        
        result = await _reflect_on_findings("What is AI?", findings, 1, tool_context, 10, None)
        
        assert isinstance(result, ReflectionResult)
        assert result.quality_score == 0.5
        assert "LLM reflection error" in result.gaps
    
    async def test_respects_max_iterations(self):
        """Test that should_continue respects max_iterations."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response that says to continue
        mock_response = MagicMock()
        mock_response.text = '''{
            "quality_score": 0.5,
            "gaps": ["Need more"],
            "should_continue": true,
            "suggested_queries": ["more queries"],
            "reasoning": "Continue"
        }'''
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        findings = []
        
        # At max iterations, should_continue should be False
        result = await _reflect_on_findings("What is AI?", findings, 10, tool_context, 10, None)
        
        assert result.should_continue is False


@pytest.mark.asyncio
class TestSelectSourcesToFetch:
    """Tests for _select_sources_to_fetch async function."""
    
    def _create_mock_tool_context(self, canonical_model=None):
        """Helper to create a mock tool context with a model."""
        mock_context = MagicMock()
        mock_inv_context = MagicMock()
        mock_agent = MagicMock()
        mock_agent.canonical_model = canonical_model
        mock_agent.host_component = None
        mock_inv_context.agent = mock_agent
        mock_context._invocation_context = mock_inv_context
        return mock_context
    
    async def test_returns_empty_list_for_no_web_findings(self):
        """Test that empty list is returned when no web findings."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        # Only KB findings, no web
        findings = [
            SearchResult(source_type="kb", title="KB Source", content="Content", url=None)
        ]
        
        result = await _select_sources_to_fetch("What is AI?", findings, 3, tool_context, None)
        
        assert result == []
    
    async def test_returns_selected_sources_from_llm(self):
        """Test that sources are selected based on LLM response."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with selected indices
        mock_response = MagicMock()
        mock_response.text = '{"selected_sources": [1, 3], "reasoning": "Best sources"}'
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        findings = [
            SearchResult(source_type="web", title="Source 1", content="Content 1", url="https://example1.com", relevance_score=0.9),
            SearchResult(source_type="web", title="Source 2", content="Content 2", url="https://example2.com", relevance_score=0.8),
            SearchResult(source_type="web", title="Source 3", content="Content 3", url="https://example3.com", relevance_score=0.7),
        ]
        
        result = await _select_sources_to_fetch("What is AI?", findings, 3, tool_context, None)
        
        assert len(result) == 2
        assert result[0].title == "Source 1"
        assert result[1].title == "Source 3"
    
    async def test_returns_fallback_on_empty_response(self):
        """Test that fallback selection is used on empty response."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with empty text
        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        findings = [
            SearchResult(source_type="web", title="Source 1", content="Content 1", url="https://example1.com", relevance_score=0.9),
            SearchResult(source_type="web", title="Source 2", content="Content 2", url="https://example2.com", relevance_score=0.8),
        ]
        
        result = await _select_sources_to_fetch("What is AI?", findings, 2, tool_context, None)
        
        # Should return top sources by relevance
        assert len(result) == 2
        assert result[0].relevance_score >= result[1].relevance_score
    
    async def test_returns_fallback_on_exception(self):
        """Test that fallback selection is used on exception."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Make generate_content_async raise an exception
        mock_model.generate_content_async = MagicMock(side_effect=Exception("LLM error"))
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        findings = [
            SearchResult(source_type="web", title="Source 1", content="Content 1", url="https://example1.com", relevance_score=0.9),
            SearchResult(source_type="web", title="Source 2", content="Content 2", url="https://example2.com", relevance_score=0.8),
        ]
        
        result = await _select_sources_to_fetch("What is AI?", findings, 2, tool_context, None)
        
        # Should return top sources by relevance
        assert len(result) == 2
    
    async def test_limits_to_max_to_fetch(self):
        """Test that results are limited to max_to_fetch."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response with more indices than max_to_fetch
        mock_response = MagicMock()
        mock_response.text = '{"selected_sources": [1, 2, 3, 4, 5], "reasoning": "All sources"}'
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        tool_context = self._create_mock_tool_context(canonical_model=mock_model)
        
        findings = [
            SearchResult(source_type="web", title=f"Source {i}", content=f"Content {i}", url=f"https://example{i}.com", relevance_score=0.9-i*0.1)
            for i in range(5)
        ]
        
        result = await _select_sources_to_fetch("What is AI?", findings, 2, tool_context, None)
        
        assert len(result) <= 2


@pytest.mark.asyncio
class TestSendDeepResearchReportSignal:
    """Tests for _send_deep_research_report_signal async function.
    
    Function signature: _send_deep_research_report_signal(artifact_filename, artifact_version, title, sources_count, tool_context)
    """
    
    def _create_mock_tool_context(self, a2a_context=None, invocation_context=None, agent=None, host_component=None):
        """Helper to create a mock tool context."""
        mock_context = MagicMock()
        mock_context.state = MagicMock()
        mock_context.state.get = MagicMock(return_value=a2a_context)
        
        if invocation_context is None:
            invocation_context = MagicMock()
            if agent is None:
                agent = MagicMock()
                agent.host_component = host_component
            invocation_context.agent = agent
        
        mock_context._invocation_context = invocation_context
        
        return mock_context
    
    async def test_returns_early_when_no_a2a_context(self):
        """Test that function returns early when no a2a_context is found."""
        tool_context = self._create_mock_tool_context(a2a_context=None)
        
        # Should not raise, just return early
        # Signature: _send_deep_research_report_signal(artifact_filename, artifact_version, title, sources_count, tool_context)
        await _send_deep_research_report_signal("report.md", 1, "Test Title", 5, tool_context)
        
        # Verify state.get was called
        tool_context.state.get.assert_called_once_with("a2a_context")
    
    async def test_returns_early_when_no_invocation_context(self):
        """Test that function returns early when no invocation context is found."""
        mock_context = MagicMock()
        mock_context.state = MagicMock()
        mock_context.state.get = MagicMock(return_value={"task_id": "test"})
        mock_context._invocation_context = None
        
        # Should not raise, just return early
        await _send_deep_research_report_signal("report.md", 1, "Test Title", 5, mock_context)
    
    async def test_returns_early_when_no_agent(self):
        """Test that function returns early when no agent is found."""
        mock_inv_context = MagicMock()
        mock_inv_context.agent = None
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            invocation_context=mock_inv_context
        )
        
        # Should not raise, just return early
        await _send_deep_research_report_signal("report.md", 1, "Test Title", 5, tool_context)
    
    async def test_returns_early_when_no_host_component(self):
        """Test that function returns early when no host component is found."""
        mock_agent = MagicMock()
        mock_agent.host_component = None
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            agent=mock_agent
        )
        
        # Should not raise, just return early
        await _send_deep_research_report_signal("report.md", 1, "Test Title", 5, tool_context)
    
    async def test_sends_report_signal_successfully(self):
        """Test that report signal is sent successfully."""
        mock_host_component = MagicMock()
        mock_agent = MagicMock()
        mock_agent.host_component = mock_host_component
        
        mock_inv_context = MagicMock()
        mock_inv_context.agent = mock_agent
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            invocation_context=mock_inv_context,
            agent=mock_agent,
            host_component=mock_host_component
        )
        
        # Patch at the source module where get_original_session_id is imported from
        with patch('solace_agent_mesh.agent.utils.context_helpers.get_original_session_id') as mock_session_id:
            mock_session_id.return_value = "test-session-123"
            
            with patch('solace_agent_mesh.common.data_parts.DeepResearchReportData') as mock_report_data:
                mock_report_data.return_value = MagicMock()
                
                await _send_deep_research_report_signal("ai_report.md", 1, "AI Overview", 10, tool_context)
                
                # Verify DeepResearchReportData was created
                mock_report_data.assert_called_once()
                call_kwargs = mock_report_data.call_args[1]
                assert call_kwargs["filename"] == "ai_report.md"
                assert call_kwargs["version"] == 1
                assert call_kwargs["title"] == "AI Overview"
                assert call_kwargs["sources_count"] == 10
    
    async def test_handles_exception_gracefully(self):
        """Test that exceptions are caught and logged."""
        mock_host_component = MagicMock()
        mock_host_component.publish_data_signal_from_thread.side_effect = Exception("Test error")
        mock_agent = MagicMock()
        mock_agent.host_component = mock_host_component
        
        mock_inv_context = MagicMock()
        mock_inv_context.agent = mock_agent
        
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            invocation_context=mock_inv_context,
            agent=mock_agent,
            host_component=mock_host_component
        )
        
        # Patch at the source module where get_original_session_id is imported from
        with patch('solace_agent_mesh.agent.utils.context_helpers.get_original_session_id') as mock_session_id:
            mock_session_id.return_value = "test-session-123"
            
            # Should not raise, just log the error
            await _send_deep_research_report_signal("report.md", 1, "Test Title", 5, tool_context)


@pytest.mark.asyncio
class TestSearchWeb:
    """Tests for _search_web async function.
    
    Function signature: _search_web(query, max_results, tool_context, tool_config, send_progress=True)
    """
    
    def _create_mock_tool_context(self, a2a_context=None, agent=None, host_component=None):
        """Helper to create a mock tool context."""
        mock_context = MagicMock()
        mock_context.state = MagicMock()
        mock_context.state.get = MagicMock(return_value=a2a_context)
        
        mock_inv_context = MagicMock()
        if agent is None:
            agent = MagicMock()
            agent.host_component = host_component
        mock_inv_context.agent = agent
        mock_context._invocation_context = mock_inv_context
        
        return mock_context
    
    async def test_returns_search_results_on_success(self):
        """Test that search results are returned on successful search."""
        tool_context = self._create_mock_tool_context(a2a_context={"task_id": "test"})
        
        # Mock the web_search_google to return proper format
        mock_result = {
            "result": '{"organic": [{"title": "Result 1", "snippet": "Snippet 1", "link": "https://example1.com"}, {"title": "Result 2", "snippet": "Snippet 2", "link": "https://example2.com"}]}'
        }
        
        with patch('solace_agent_mesh.agent.tools.deep_research_tools.web_search_google', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_result
            
            # Signature: _search_web(query, max_results, tool_context, tool_config, send_progress=True)
            results = await _search_web("test query", 10, tool_context, None, send_progress=False)
            
            assert len(results) == 2
            assert results[0].title == "Result 1"
            assert results[0].content == "Snippet 1"
            assert results[0].url == "https://example1.com"
            assert results[0].source_type == "web"
    
    async def test_returns_empty_list_on_search_failure(self):
        """Test that empty list is returned when search fails."""
        tool_context = self._create_mock_tool_context(a2a_context={"task_id": "test"})
        
        with patch('solace_agent_mesh.agent.tools.deep_research_tools.web_search_google', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("Search failed")
            
            results = await _search_web("test query", 10, tool_context, None, send_progress=False)
            
            assert results == []
    
    async def test_returns_empty_list_when_no_results(self):
        """Test that empty list is returned when search returns no results."""
        tool_context = self._create_mock_tool_context(a2a_context={"task_id": "test"})
        
        with patch('solace_agent_mesh.agent.tools.deep_research_tools.web_search_google', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = None
            
            results = await _search_web("test query", 10, tool_context, None, send_progress=False)
            
            assert results == []
    
    async def test_uses_tool_config_for_search(self):
        """Test that tool config is passed to search function."""
        tool_context = self._create_mock_tool_context(a2a_context={"task_id": "test"})
        
        tool_config = {
            "google_api_key": "test-api-key",
            "google_cse_id": "test-cse-id",
        }
        
        with patch('solace_agent_mesh.agent.tools.deep_research_tools.web_search_google', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"result": '{"organic": []}'}
            
            await _search_web("test query", 10, tool_context, tool_config, send_progress=False)
            
            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args[1]
            assert call_kwargs.get("tool_config") == tool_config


@pytest.mark.asyncio
class TestMultiSourceSearch:
    """Tests for _multi_source_search async function.
    
    Function signature: _multi_source_search(query, sources, max_results_per_source, kb_ids, tool_context, tool_config)
    """
    
    def _create_mock_tool_context(self, a2a_context=None, agent=None, host_component=None):
        """Helper to create a mock tool context."""
        mock_context = MagicMock()
        mock_context.state = MagicMock()
        mock_context.state.get = MagicMock(return_value=a2a_context)
        
        mock_inv_context = MagicMock()
        if agent is None:
            agent = MagicMock()
            agent.host_component = host_component
        mock_inv_context.agent = agent
        mock_context._invocation_context = mock_inv_context
        
        return mock_context
    
    async def test_executes_web_search(self):
        """Test that web search is executed when 'web' is in sources."""
        tool_context = self._create_mock_tool_context(a2a_context={"task_id": "test"})
        
        # Mock _search_web to return SearchResult objects
        mock_results = [
            SearchResult(source_type="web", title="Result 1", content="Snippet 1", url="https://example1.com", relevance_score=0.9),
        ]
        
        with patch('solace_agent_mesh.agent.tools.deep_research_tools._search_web', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_results
            
            # Signature: _multi_source_search(query, sources, max_results_per_source, kb_ids, tool_context, tool_config)
            results = await _multi_source_search("test query", ["web"], 5, None, tool_context, None)
            
            assert len(results) >= 1
            # Check that web results are included
            web_results = [r for r in results if r.source_type == "web"]
            assert len(web_results) >= 1
    
    async def test_deduplicates_by_url(self):
        """Test that results are deduplicated by URL."""
        tool_context = self._create_mock_tool_context(a2a_context={"task_id": "test"})
        
        # Return duplicate URLs
        mock_results = [
            SearchResult(source_type="web", title="Result 1", content="Snippet 1", url="https://example.com", relevance_score=0.9),
            SearchResult(source_type="web", title="Result 2", content="Snippet 2", url="https://example.com", relevance_score=0.8),  # Duplicate URL
        ]
        
        with patch('solace_agent_mesh.agent.tools.deep_research_tools._search_web', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_results
            
            results = await _multi_source_search("test query", ["web"], 5, None, tool_context, None)
            
            # Should only have one result due to deduplication
            urls = [r.url for r in results if r.url]
            unique_urls = set(urls)
            assert len(urls) == len(unique_urls)
    
    async def test_handles_search_exception(self):
        """Test that search exceptions are handled gracefully."""
        tool_context = self._create_mock_tool_context(a2a_context={"task_id": "test"})
        
        with patch('solace_agent_mesh.agent.tools.deep_research_tools._search_web', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("Search failed")
            
            # Should not raise, just return empty or partial results
            results = await _multi_source_search("test query", ["web"], 5, None, tool_context, None)
            
            assert isinstance(results, list)
    
    async def test_sorts_by_relevance(self):
        """Test that results are sorted by relevance score."""
        tool_context = self._create_mock_tool_context(a2a_context={"task_id": "test"})
        
        mock_results = [
            SearchResult(source_type="web", title="Low relevance", content="Snippet 1", url="https://example1.com", relevance_score=0.5),
            SearchResult(source_type="web", title="High relevance", content="Snippet 2", url="https://example2.com", relevance_score=0.9),
        ]
        
        with patch('solace_agent_mesh.agent.tools.deep_research_tools._search_web', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_results
            
            results = await _multi_source_search("test query", ["web"], 5, None, tool_context, None)
            
            # Results should be sorted by relevance (higher first)
            if len(results) >= 2:
                for i in range(len(results) - 1):
                    assert results[i].relevance_score >= results[i + 1].relevance_score


@pytest.mark.asyncio
class TestFetchSelectedSources:
    """Tests for _fetch_selected_sources async function.
    
    Function signature: _fetch_selected_sources(selected_sources, tool_context, tool_config, citation_tracker, start_time=0, max_runtime_seconds=None)
    Returns: Dict[str, int] with 'success' and 'failed' counts
    """
    
    def _create_mock_tool_context(self, a2a_context=None, agent=None, host_component=None):
        """Helper to create a mock tool context."""
        mock_context = MagicMock()
        mock_context.state = MagicMock()
        mock_context.state.get = MagicMock(return_value=a2a_context)
        
        mock_inv_context = MagicMock()
        if agent is None:
            agent = MagicMock()
            agent.host_component = host_component
        mock_inv_context.agent = agent
        mock_context._invocation_context = mock_inv_context
        
        return mock_context
    
    async def test_returns_stats_for_empty_sources(self):
        """Test that stats dict is returned when no sources provided."""
        tool_context = self._create_mock_tool_context(a2a_context={"task_id": "test"})
        tracker = ResearchCitationTracker("Test question")
        
        # Signature: _fetch_selected_sources(selected_sources, tool_context, tool_config, citation_tracker, start_time=0, max_runtime_seconds=None)
        result = await _fetch_selected_sources([], tool_context, None, tracker)
        
        # Returns dict with success/failed counts
        assert result == {"success": 0, "failed": 0}
    
    async def test_fetches_content_successfully(self):
        """Test that content is fetched successfully."""
        mock_host_component = MagicMock()
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            host_component=mock_host_component
        )
        tracker = ResearchCitationTracker("Test question")
        
        sources = [
            SearchResult(source_type="web", title="Source 1", content="Snippet", url="https://example.com", relevance_score=0.9)
        ]
        
        with patch('solace_agent_mesh.agent.tools.deep_research_tools.web_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"status": "success", "result_preview": "Full content here"}
            
            result = await _fetch_selected_sources(sources, tool_context, None, tracker)
            
            # Returns dict with success/failed counts
            assert result["success"] == 1
            assert result["failed"] == 0
            # Source should be marked as fetched
            assert sources[0].metadata.get("fetched") is True
    
    async def test_handles_fetch_failure(self):
        """Test that fetch failures are handled gracefully."""
        mock_host_component = MagicMock()
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            host_component=mock_host_component
        )
        tracker = ResearchCitationTracker("Test question")
        
        sources = [
            SearchResult(source_type="web", title="Source 1", content="Snippet", url="https://example.com", relevance_score=0.9)
        ]
        
        with patch('solace_agent_mesh.agent.tools.deep_research_tools.web_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("Fetch failed")
            
            result = await _fetch_selected_sources(sources, tool_context, None, tracker)
            
            # Should return stats with failed count
            assert result["success"] == 0
            assert result["failed"] == 1
    
    async def test_updates_citation_tracker(self):
        """Test that citation tracker is updated with fetched sources."""
        mock_host_component = MagicMock()
        tool_context = self._create_mock_tool_context(
            a2a_context={"task_id": "test"},
            host_component=mock_host_component
        )
        tracker = ResearchCitationTracker("Test question")
        
        # Add citation first so it can be updated
        source = SearchResult(source_type="web", title="Source 1", content="Snippet", url="https://example.com", relevance_score=0.9)
        tracker.add_citation(source)
        
        sources = [source]
        
        with patch('solace_agent_mesh.agent.tools.deep_research_tools.web_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"status": "success", "result_preview": "Full content"}
            
            await _fetch_selected_sources(sources, tool_context, None, tracker)
            
            # Citation should have been updated
            assert tracker.citation_counter >= 1


@pytest.mark.asyncio
class TestGenerateResearchReport:
    """Tests for _generate_research_report async function."""
    
    def _create_mock_tool_context(self, canonical_model=None, a2a_context=None, host_component=None):
        """Helper to create a mock tool context with a model."""
        mock_context = MagicMock()
        mock_context.state = MagicMock()
        mock_context.state.get = MagicMock(return_value=a2a_context)
        
        mock_inv_context = MagicMock()
        mock_agent = MagicMock()
        mock_agent.canonical_model = canonical_model
        mock_agent.host_component = host_component
        mock_inv_context.agent = mock_agent
        mock_context._invocation_context = mock_inv_context
        return mock_context
    
    async def test_generates_report_from_llm(self):
        """Test that report is generated from LLM response."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock streaming response
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "# Research Report\n\n"
        mock_chunk1.parts = None
        mock_chunk1.content = None
        
        mock_chunk2 = MagicMock()
        mock_chunk2.text = "This is the report content."
        mock_chunk2.parts = None
        mock_chunk2.content = None
        
        async def mock_generate():
            yield mock_chunk1
            yield mock_chunk2
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        mock_host_component = MagicMock()
        tool_context = self._create_mock_tool_context(
            canonical_model=mock_model,
            a2a_context={"task_id": "test"},
            host_component=mock_host_component
        )
        
        tracker = ResearchCitationTracker("What is AI?")
        tracker.set_title("AI Overview")
        
        findings = [
            SearchResult(source_type="web", title="Source 1", content="Content 1", url="https://example.com", relevance_score=0.9)
        ]
        tracker.add_citation(findings[0])
        
        report = await _generate_research_report("What is AI?", findings, tracker, tool_context, None)
        
        assert "# Research Report" in report
        assert "This is the report content." in report
    
    async def test_includes_sources_section(self):
        """Test that report includes sources section."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Create mock response
        mock_response = MagicMock()
        mock_response.text = "# Report\n\nContent here."
        mock_response.parts = None
        mock_response.content = None
        
        async def mock_generate():
            yield mock_response
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        mock_host_component = MagicMock()
        tool_context = self._create_mock_tool_context(
            canonical_model=mock_model,
            a2a_context={"task_id": "test"},
            host_component=mock_host_component
        )
        
        tracker = ResearchCitationTracker("What is AI?")
        
        findings = [
            SearchResult(source_type="web", title="Source 1", content="Content 1", url="https://example.com", relevance_score=0.9)
        ]
        findings[0].citation_id = "research0"
        tracker.citations["research0"] = findings[0]
        
        report = await _generate_research_report("What is AI?", findings, tracker, tool_context, None)
        
        # Report should include references section
        assert "References" in report or "Source" in report
    
    async def test_handles_llm_exception(self):
        """Test that LLM exceptions are handled gracefully."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        # Make generate_content_async raise an exception
        mock_model.generate_content_async = MagicMock(side_effect=Exception("LLM error"))
        
        mock_host_component = MagicMock()
        tool_context = self._create_mock_tool_context(
            canonical_model=mock_model,
            a2a_context={"task_id": "test"},
            host_component=mock_host_component
        )
        
        tracker = ResearchCitationTracker("What is AI?")
        findings = []
        
        # Should return an error message instead of raising
        report = await _generate_research_report("What is AI?", findings, tracker, tool_context, None)
        
        assert "error" in report.lower() or "failed" in report.lower() or report == ""
    
    async def test_streams_report_content(self):
        """Test that report content is streamed."""
        mock_model = MagicMock()
        mock_model.model = "gpt-4"
        
        chunks_received = []
        
        # Create mock streaming response with multiple chunks
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "Part 1. "
        mock_chunk1.parts = None
        mock_chunk1.content = None
        
        mock_chunk2 = MagicMock()
        mock_chunk2.text = "Part 2. "
        mock_chunk2.parts = None
        mock_chunk2.content = None
        
        mock_chunk3 = MagicMock()
        mock_chunk3.text = "Part 3."
        mock_chunk3.parts = None
        mock_chunk3.content = None
        
        async def mock_generate():
            for chunk in [mock_chunk1, mock_chunk2, mock_chunk3]:
                chunks_received.append(chunk.text)
                yield chunk
        
        mock_model.generate_content_async = MagicMock(return_value=mock_generate())
        
        mock_host_component = MagicMock()
        tool_context = self._create_mock_tool_context(
            canonical_model=mock_model,
            a2a_context={"task_id": "test"},
            host_component=mock_host_component
        )
        
        tracker = ResearchCitationTracker("What is AI?")
        findings = []
        
        report = await _generate_research_report("What is AI?", findings, tracker, tool_context, None)
        
        # Verify all chunks were processed
        assert len(chunks_received) == 3
        assert "Part 1. Part 2. Part 3." in report
