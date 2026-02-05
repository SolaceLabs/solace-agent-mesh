"""
Deep Research Tools for Solace Agent Mesh

Provides comprehensive, iterative research capabilities using web search

This module implements:
- Iterative research with LLM-powered reflection and query refinement
- Multi-source search coordination
- Citation tracking and management
- Progress updates to frontend
- Comprehensive report generation
"""

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

from google.adk.tools import ToolContext
from google.genai import types as adk_types
from google.adk.models import LlmRequest
from solace_ai_connector.common.log import log

from .tool_definition import BuiltinTool
from .registry import tool_registry
from .web_search_tools import web_search_google
from .web_tools import web_request
from ...common import a2a
from ...common.rag_dto import create_rag_source, create_rag_search_result


# Category information
CATEGORY_NAME = "Research & Analysis"
CATEGORY_DESCRIPTION = "Advanced research tools for comprehensive information gathering"


def _extract_text_from_llm_response(response: Any, log_identifier: str = "[LLM]") -> str:
    """
    Extract text from various LLM response formats.
    
    Handles multiple response structures:
    - Direct text attribute (response.text)
    - Parts attribute for streaming responses (response.parts)
    - Content attribute with parts for LlmResponse objects (response.content.parts)
    
    Args:
        response: The LLM response object
        log_identifier: Identifier for logging
    
    Returns:
        Extracted text string, or empty string if extraction fails
    """
    response_text = ""
    
    # Method 1: Direct text attribute
    if hasattr(response, 'text') and response.text:
        response_text = response.text
    # Method 2: Parts attribute (for streaming responses)
    elif hasattr(response, 'parts') and response.parts:
        response_text = "".join([part.text for part in response.parts if hasattr(part, 'text') and part.text])
    # Method 3: Content attribute with parts (for LlmResponse objects from Gemini 2.5 Pro)
    elif hasattr(response, 'content') and response.content:
        content = response.content
        if hasattr(content, 'parts') and content.parts:
            response_text = "".join([part.text for part in content.parts if hasattr(part, 'text') and part.text])
        elif hasattr(content, 'text') and content.text:
            response_text = content.text
        elif isinstance(content, str):
            response_text = content
    
    if not response_text or not response_text.strip():
        log.warning("%s Could not extract text from LLM response. Response type: %s",
                   log_identifier, type(response).__name__)
        if response:
            log.debug("%s Response attributes: text=%s, parts=%s, content=%s",
                     log_identifier,
                     hasattr(response, 'text'),
                     hasattr(response, 'parts'),
                     hasattr(response, 'content'))
    
    return response_text


def _parse_json_from_llm_response(
    response_text: str,
    log_identifier: str = "[LLM]",
    fallback_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Parse JSON from LLM response text, handling markdown code blocks.
    
    Gemini 2.5 Pro and other models often wrap JSON in markdown code blocks
    (```json ... ```) even when response_mime_type="application/json" is set.
    This function handles that case.
    
    Args:
        response_text: The raw response text from the LLM
        log_identifier: Identifier for logging
        fallback_key: Optional key to search for in regex fallback (e.g., "queries", "selected_sources")
    
    Returns:
        Parsed JSON dict, or None if parsing fails
    """
    if not response_text or not response_text.strip():
        log.warning("%s Empty response text, cannot parse JSON", log_identifier)
        return None
    
    # Strip markdown code block wrapper if present (common with Gemini 2.5 Pro)
    clean_text = response_text.strip()
    if clean_text.startswith('```'):
        # Remove opening ```json or ``` and closing ```
        if clean_text.startswith('```json'):
            clean_text = clean_text[7:]  # len('```json') = 7
        else:
            clean_text = clean_text[3:]  # len('```') = 3
        clean_text = clean_text.lstrip() 
        
        # Remove closing ``` and trailing whitespace
        clean_text = clean_text.rstrip()
        if clean_text.endswith('```'):
            clean_text = clean_text[:-3]  # Remove trailing ```
            clean_text = clean_text.rstrip()  # Remove any whitespace before closing ```
        log.debug("%s Stripped markdown code block wrapper", log_identifier)
    
    # Try to parse JSON directly
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError as je:
        log.warning("%s Failed to parse LLM JSON response: %s. Response text: %s",
                   log_identifier, str(je), clean_text[:200])
    
    # Fallback: Try to extract JSON from markdown code blocks (in case stripping didn't work)
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            result = json.loads(json_match.group(1))
            log.info("%s Extracted JSON from markdown code block", log_identifier)
            return result
        except json.JSONDecodeError:
            log.warning("%s Failed to parse extracted JSON from code block", log_identifier)
    
    # Fallback: Try to find any JSON object with the specified key
    if fallback_key:
        # Build a regex pattern to find JSON with the specified key
        json_match = re.search(rf'\{{[^{{}}]*"{fallback_key}"[^{{}}]*\}}', response_text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                log.info("%s Extracted JSON object with key '%s' from response", log_identifier, fallback_key)
                return result
            except json.JSONDecodeError:
                log.warning("%s Failed to parse extracted JSON object with key '%s'", log_identifier, fallback_key)
    
    log.warning("%s No valid JSON found in response", log_identifier)
    return None


@dataclass
class SearchResult:
    """Represents a single search result from any source (web-only version)"""
    source_type: str  # "web" only, for now
    title: str
    content: str
    url: Optional[str] = None
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    citation_id: Optional[str] = None


@dataclass
class ReflectionResult:
    """Result of reflecting on current research findings"""
    quality_score: float  # 0-1 score of information completeness
    gaps: List[str]  # Identified knowledge gaps
    should_continue: bool  # Whether more research is needed
    suggested_queries: List[str]  # New queries to explore gaps
    reasoning: str  # Explanation of the reflection

def _get_model_for_phase(
    phase: str,
    tool_context: ToolContext,
    tool_config: Optional[Dict[str, Any]]
):
    """
    Get the appropriate model for a specific research phase.
    
    Supports phase-specific model configuration for cost optimization,
    speed tuning, and quality control.
    
    Args:
        phase: One of 'query_generation', 'reflection', 'source_selection', 'report_generation'
        tool_context: Tool context for accessing agent
        tool_config: Tool configuration with optional phase-specific models
    
    Returns:
        BaseLlm instance for the phase (either phase-specific or agent default)
        
    Configuration Examples:
        # Simple model names:
        tool_config:
          models:
            query_generation: "gpt-4o-mini"
            report_generation: "claude-3-5-sonnet-20241022"
        
        # Full model configs with parameters:
        tool_config:
          model_configs:
            report_generation:
              model: "claude-3-5-sonnet-20241022"
              temperature: 0.7
              max_tokens: 16000
    """
    log_identifier = f"[DeepResearch:ModelSelection:{phase}]"
    
    # Get agent's default model 
    inv_context = tool_context._invocation_context
    agent = getattr(inv_context, 'agent', None)
    default_model = agent.canonical_model if agent else None
    
    # If canonical_model is not available, try to get model from host_component config
    if not default_model:
        host_component = getattr(agent, "host_component", None) if agent else None
        if host_component:
            model_config_from_component = host_component.get_config("model")
            if model_config_from_component:
                log.info(
                    "%s canonical_model not available, falling back to host_component model config",
                    log_identifier,
                )
                from ...agent.adk.models.lite_llm import LiteLlm
                if isinstance(model_config_from_component, str):
                    default_model = LiteLlm(model=model_config_from_component)
                elif isinstance(model_config_from_component, dict):
                    default_model = LiteLlm(**model_config_from_component)
    
    if not default_model:
        raise ValueError(f"{log_identifier} No default model available")
    
    # Check for phase-specific configuration
    if not tool_config:
        log.debug("%s No tool_config, using agent default model", log_identifier)
        return default_model
    
    # Helper function to copy base config from default model
    def _get_base_config_from_default():
        """Extract base configuration from default model to inherit API keys and settings"""
        base_config = {}
        if hasattr(default_model, '_additional_args') and default_model._additional_args:
            # Copy relevant config from default model (API keys, timeouts, custom endpoints, etc.)
            # Exclude model-specific params that shouldn't be inherited
            # Also exclude max_completion_tokens to avoid conflicts with max_tokens
            exclude_keys = {'model', 'messages', 'tools', 'stream', 'temperature', 'max_tokens',
                          'max_output_tokens', 'max_completion_tokens', 'top_p', 'top_k'}
            base_config = {k: v for k, v in default_model._additional_args.items()
                          if k not in exclude_keys}
            
            # Log inherited configuration for debugging
            if base_config:
                log.debug("%s Inheriting base config from default model: api_base=%s, api_key=%s",
                         log_identifier,
                         base_config.get('api_base', 'default'),
                         'present' if base_config.get('api_key') else 'missing')
        return base_config
    
    # Option 1: Simple model name string
    models_config = tool_config.get("models", {})
    if phase in models_config:
        model_name = models_config[phase]
        if isinstance(model_name, str):
            log.info("%s Using phase-specific model: %s", log_identifier, model_name)
            from ...agent.adk.models.lite_llm import LiteLlm
            # Inherit base config from default model (API keys, etc.)
            base_config = _get_base_config_from_default()
            return LiteLlm(model=model_name, **base_config)
    
    # Option 2: Full model configuration dict
    model_configs = tool_config.get("model_configs", {})
    if phase in model_configs:
        model_config = model_configs[phase]
        if isinstance(model_config, dict):
            model_name = model_config.get("model")
            log.info("%s Using phase-specific model config: %s (temp=%.1f, max_tokens=%s)",
                    log_identifier, model_name,
                    model_config.get("temperature", 0.7),
                    model_config.get("max_tokens", "default"))
            from ...agent.adk.models.lite_llm import LiteLlm
            # Inherit base config from default model, but allow override
            base_config = _get_base_config_from_default()
            # Merge: base_config first, then model_config (model_config takes precedence)
            merged_config = {**base_config, **model_config}
            
            # Additional safety: if max_tokens is specified, ensure max_completion_tokens is not present
            if 'max_tokens' in merged_config and 'max_completion_tokens' in merged_config:
                log.debug("%s Removing max_completion_tokens to avoid conflict with max_tokens", log_identifier)
                del merged_config['max_completion_tokens']
            
            return LiteLlm(**merged_config)
    
    # Fallback to agent default
    log.debug("%s No phase-specific model configured, using agent default", log_identifier)
    return default_model


class ResearchCitationTracker:
    """Tracks citations throughout the research process"""
    
    def __init__(self, research_question: str):
        self.research_question = research_question
        self.citations: Dict[str, Dict[str, Any]] = {}
        self.citation_counter = 0
        self.source_to_citation: Dict[str, str] = {}  # Map URL to citation_id for updates
        self.queries: List[Dict[str, Any]] = []  # Track queries and their sources
        self.current_query: Optional[str] = None
        self.current_query_sources: List[str] = []
        self.generated_title: Optional[str] = None  # LLM-generated human-readable title
    
    def set_title(self, title: str) -> None:
        """Set the LLM-generated title for this research"""
        self.generated_title = title
    
    def start_query(self, query: str):
        """Start tracking a new query"""
        # Save previous query if it exists
        if self.current_query:
            self.queries.append({
                "query": self.current_query,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_citation_ids": self.current_query_sources.copy()
            })
        
        # Start new query
        self.current_query = query
        self.current_query_sources = []
    
    def add_citation(self, result: SearchResult, query: Optional[str] = None) -> str:
        """Add citation and return citation ID"""
        # Use 'research' prefix to match the citation rendering system for deep research
        citation_id = f"research{self.citation_counter}"
        log.info("[DeepResearch:Citation] Creating citation_id=%s (counter=%d) for: %s",
                 citation_id, self.citation_counter, result.title[:50])
        self.citation_counter += 1
        
        # Create citation using DTO helper for camelCase conversion
        citation_dict = create_rag_source(
            citation_id=citation_id,
            file_id=f"deep_research_{self.citation_counter}",
            filename=result.title,
            title=result.title,
            source_url=result.url or "N/A",
            url=result.url,
            content_preview=result.content[:200] + "..." if len(result.content) > 200 else result.content,
            relevance_score=result.relevance_score,
            source_type=result.source_type,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "title": result.title,
                "link": result.url,
                "type": "web_search",
                "source_type": result.source_type,
                "favicon": f"https://www.google.com/s2/favicons?domain={result.url}&sz=32" if result.url else "",
                **result.metadata
            }
        )
        
        self.citations[citation_id] = citation_dict
        result.citation_id = citation_id
        
        # Track URL to citation_id mapping for later updates
        if result.url:
            self.source_to_citation[result.url] = citation_id
        
        # Track this citation for the current query
        if self.current_query:
            self.current_query_sources.append(citation_id)
        
        return citation_id
    
    def update_citation_after_fetch(self, result: SearchResult) -> None:
        """Update citation with fetched content and metadata"""
        if not result.url or result.url not in self.source_to_citation:
            return
        
        citation_id = self.source_to_citation[result.url]
        if citation_id in self.citations:
            # Update content preview with fetched content
            self.citations[citation_id]["content_preview"] = result.content[:500] + "..." if len(result.content) > 500 else result.content
            # Update metadata with fetched flag
            self.citations[citation_id]["metadata"]["fetched"] = result.metadata.get("fetched", False)
            self.citations[citation_id]["metadata"]["fetch_status"] = result.metadata.get("fetch_status", "")
            log.info("[DeepResearch:Citation] Updated citation %s with fetched content", citation_id)
    
    def get_rag_metadata(self, artifact_filename: Optional[str] = None) -> Dict[str, Any]:
        """Format citations for RAG system with camelCase conversion"""
        # Save the last query if it exists
        if self.current_query:
            self.queries.append({
                "query": self.current_query,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_citation_ids": self.current_query_sources.copy()
            })
            self.current_query = None
            self.current_query_sources = []
        
        # Build metadata dict
        metadata_dict: Dict[str, Any] = {
            "queries": self.queries  # Include query breakdown for timeline
        }
        
        # Include artifact filename if provided (for matching after page refresh)
        if artifact_filename:
            metadata_dict["artifactFilename"] = artifact_filename
        
        # Return single search result with all sources using DTO for camelCase conversion
        return create_rag_search_result(
            query=self.research_question,
            search_type="deep_research",
            timestamp=datetime.now(timezone.utc).isoformat(),
            sources=list(self.citations.values()),
            metadata=metadata_dict,
            title=self.generated_title  
        )


async def _send_research_progress(
    message: str,
    tool_context: ToolContext,
    phase: str = "",
    progress_percentage: int = 0,
    current_iteration: int = 0,
    total_iterations: int = 0,
    sources_found: int = 0,
    current_query: str = "",
    fetching_urls: Optional[List[Dict[str, str]]] = None,
    elapsed_seconds: int = 0,
    max_runtime_seconds: int = 0
) -> None:
    """Send research progress update to frontend via SSE with structured data"""
    log_identifier = "[DeepResearch:Progress]"
    
    try:
        # Get a2a context from tool context state
        a2a_context = tool_context.state.get("a2a_context")
        if not a2a_context:
            log.warning("%s No a2a_context found, cannot send progress update", log_identifier)
            return

        # Get the host component from invocation context
        invocation_context = getattr(tool_context, '_invocation_context', None)
        if not invocation_context:
            log.warning("%s No invocation context found", log_identifier)
            return
            
        agent = getattr(invocation_context, 'agent', None)
        if not agent:
            log.warning("%s No agent found in invocation context", log_identifier)
            return
            
        host_component = getattr(agent, 'host_component', None)
        if not host_component:
            log.warning("%s No host component found on agent", log_identifier)
            return

        log.info("%s Sending progress: %s", log_identifier, message)

        # Use structured DeepResearchProgressData if phase is provided, otherwise simple text
        from ...common.data_parts import DeepResearchProgressData, AgentProgressUpdateData
        
        if phase:
            # Send structured progress data for UI visualization
            progress_data = DeepResearchProgressData(
                phase=phase,
                status_text=message,
                progress_percentage=progress_percentage,
                current_iteration=current_iteration,
                total_iterations=total_iterations,
                sources_found=sources_found,
                current_query=current_query,
                fetching_urls=fetching_urls or [],
                elapsed_seconds=elapsed_seconds,
                max_runtime_seconds=max_runtime_seconds
            )
        else:
            # Fallback to simple text progress
            progress_data = AgentProgressUpdateData(status_text=message)
        
        # Use the host component's helper method to publish the data signal
        host_component.publish_data_signal_from_thread(
            a2a_context=a2a_context,
            signal_data=progress_data,
            skip_buffer_flush=False,
            log_identifier=log_identifier,
        )
        
    except Exception as e:
        log.error("%s Error sending progress update: %s", log_identifier, str(e))


async def _send_rag_info_update(
    citation_tracker: 'ResearchCitationTracker',
    tool_context: ToolContext,
    is_complete: bool = False
) -> None:
    """
    Send RAG info update to frontend via SSE for the RAG info panel.
    
    This sends the title and sources early so the UI can display them
    while research is still in progress.
    
    Args:
        citation_tracker: The citation tracker with title and sources
        tool_context: Tool context for accessing agent
        is_complete: Whether the research is complete
    """
    log_identifier = "[DeepResearch:RAGInfo]"
    
    try:
        # Get a2a context from tool context state
        a2a_context = tool_context.state.get("a2a_context")
        if not a2a_context:
            log.warning("%s No a2a_context found, cannot send RAG info update", log_identifier)
            return

        # Get the host component from invocation context
        invocation_context = getattr(tool_context, '_invocation_context', None)
        if not invocation_context:
            log.warning("%s No invocation context found", log_identifier)
            return
            
        agent = getattr(invocation_context, 'agent', None)
        if not agent:
            log.warning("%s No agent found in invocation context", log_identifier)
            return
            
        host_component = getattr(agent, 'host_component', None)
        if not host_component:
            log.warning("%s No host component found on agent", log_identifier)
            return

        # Get title (use research question as fallback)
        title = citation_tracker.generated_title or citation_tracker.research_question
        
        # Get sources in camelCase format for frontend
        sources = list(citation_tracker.citations.values())
        
        log.info("%s Sending RAG info update: title='%s', sources=%d, is_complete=%s",
                log_identifier, title[:50], len(sources), is_complete)

        # Import and create the RAG info update data
        from ...common.data_parts import RAGInfoUpdateData
        
        rag_info_data = RAGInfoUpdateData(
            title=title,
            query=citation_tracker.research_question,
            search_type="deep_research",
            sources=sources,
            is_complete=is_complete,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        # Use the host component's helper method to publish the data signal
        host_component.publish_data_signal_from_thread(
            a2a_context=a2a_context,
            signal_data=rag_info_data,
            skip_buffer_flush=False,
            log_identifier=log_identifier,
        )
        
    except Exception as e:
        log.error("%s Error sending RAG info update: %s", log_identifier, str(e))


async def _send_deep_research_report_signal(
    artifact_filename: str,
    artifact_version: int,
    title: str,
    sources_count: int,
    tool_context: ToolContext
) -> None:
    """
    Send DeepResearchReportData signal directly to frontend.
    
    This bypasses the LLM response entirely, ensuring the report is displayed
    via the DeepResearchReportBubble component without duplication.
    
    The frontend will receive this signal and render the report using the
    artifact viewer, suppressing any text content from the LLM response.
    
    Args:
        artifact_filename: The filename of the research report artifact
        artifact_version: The version number of the artifact
        title: Human-readable title for the research
        sources_count: Number of sources analyzed
        tool_context: Tool context for accessing agent
    """
    log_identifier = "[DeepResearch:ReportSignal]"
    
    try:
        # Get a2a context from tool context state
        a2a_context = tool_context.state.get("a2a_context")
        if not a2a_context:
            log.warning("%s No a2a_context found, cannot send report signal", log_identifier)
            return

        # Get the host component from invocation context
        invocation_context = getattr(tool_context, '_invocation_context', None)
        if not invocation_context:
            log.warning("%s No invocation context found", log_identifier)
            return
            
        agent = getattr(invocation_context, 'agent', None)
        if not agent:
            log.warning("%s No agent found in invocation context", log_identifier)
            return
            
        host_component = getattr(agent, 'host_component', None)
        if not host_component:
            log.warning("%s No host component found on agent", log_identifier)
            return

        # Build the artifact URI for the frontend
        # Format: artifact://{session_id}/{filename}?version={version}
        # This matches the format expected by parseArtifactUri in download.ts
        from ..utils.context_helpers import get_original_session_id
        session_id = get_original_session_id(invocation_context)
        artifact_uri = f"artifact://{session_id}/{artifact_filename}?version={artifact_version}"
        
        log.info("%s Sending deep research report signal: filename='%s', version=%d, uri='%s'",
                log_identifier, artifact_filename, artifact_version, artifact_uri)

        # Import and create the DeepResearchReportData
        from ...common.data_parts import DeepResearchReportData
        
        report_data = DeepResearchReportData(
            filename=artifact_filename,
            version=artifact_version,
            uri=artifact_uri,
            title=title,
            sources_count=sources_count
        )
        
        # Use the host component's helper method to publish the data signal
        host_component.publish_data_signal_from_thread(
            a2a_context=a2a_context,
            signal_data=report_data,
            skip_buffer_flush=False,
            log_identifier=log_identifier,
        )
        
        log.info("%s Successfully sent deep research report signal", log_identifier)
        
    except Exception as e:
        log.error("%s Error sending deep research report signal: %s", log_identifier, str(e))


async def _search_web(
    query: str,
    max_results: int,
    tool_context: ToolContext,
    tool_config: Optional[Dict[str, Any]],
    send_progress: bool = True
) -> List[SearchResult]:
    """Search web using Google Custom Search API.
    
    Note: For other search providers (Tavily, Exa, Brave), use the corresponding
    plugins from the solace-agent-mesh-plugins repository.
    """
    log_identifier = "[DeepResearch:WebSearch]"
    
    if send_progress:
        await _send_research_progress(
            f"Searching web for: {query[:60]}...",
            tool_context
        )
    
    try:
        log.info("%s Attempting Google search", log_identifier)
        result = await web_search_google(
            query=query,
            max_results=max_results,
            tool_context=tool_context,
            tool_config=tool_config
        )
        
        if isinstance(result, dict) and result.get("result"):
            result_data = json.loads(result["result"])
            search_results = []
            
            for item in result_data.get("organic", []):
                search_results.append(SearchResult(
                    source_type="web",
                    title=item.get("title", ""),
                    content=item.get("snippet", ""),
                    url=item.get("link", ""),
                    relevance_score=0.85,
                    metadata={"provider": "google"}
                ))
            
            log.info("%s Found %d Google results", log_identifier, len(search_results))
            return search_results
    except Exception as e:
        log.error("%s Google search failed: %s", log_identifier, str(e))
    
    log.warning("%s No web search results available - Google search failed or not configured", log_identifier)
    return []

# TODO: will add other sources such as knowledgebases
async def _multi_source_search(
    query: str,
    sources: List[str],
    max_results_per_source: int,
    kb_ids: Optional[List[str]],
    tool_context: ToolContext,
    tool_config: Optional[Dict[str, Any]]
) -> List[SearchResult]:
    """Execute search across various sources in parallel (web-only version)"""
    log_identifier = "[DeepResearch:MultiSearch]"
    log.info("%s Searching across sources: %s", log_identifier, sources)
    
    tasks = []
    
    # Web-only version - only web search
    if "web" in sources:
        tasks.append(_search_web(query, max_results_per_source, tool_context, tool_config, send_progress=False))
    
    # Execute all searches in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Flatten and filter results
    all_results = []
    for result in results:
        if isinstance(result, list):
            all_results.extend(result)
        elif isinstance(result, Exception):
            log.warning("%s Search task failed: %s", log_identifier, str(result))
    
    # Deduplicate by URL/title
    seen = set()
    unique_results = []
    for result in all_results:
        # For web sources, use URL or title as the key
        key = result.url or f"web:{result.title}"
        
        if key not in seen:
            seen.add(key)
            unique_results.append(result)
    
    # Sort by relevance score
    unique_results.sort(key=lambda x: x.relevance_score, reverse=True)
    
    log.info("%s Found %d unique results across all sources", log_identifier, len(unique_results))
    return unique_results


async def _generate_initial_queries(
    research_question: str,
    tool_context: ToolContext,
    tool_config: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Generate 3-5 initial search queries using LLM.
    The LLM breaks down the research question into effective search queries.
    
    Supports phase-specific model via tool_config.
    """
    log_identifier = "[DeepResearch:QueryGen]"
    
    try:
        # Get phase-specific or default model
        llm = _get_model_for_phase("query_generation", tool_context, tool_config)
        
        query_prompt = f"""You are a research query specialist. Generate 3-5 effective search queries to comprehensively research this question:

Research Question: {research_question}

Generate queries that:
1. Cover different aspects of the topic
2. Use varied terminology and perspectives
3. Range from broad to specific
4. Are optimized for search engines

Respond in JSON format:
{{
  "queries": ["query1", "query2", "query3", "query4", "query5"]
}}"""

        log.info("%s Calling LLM for query generation", log_identifier)
        
        # Create LLM request
        # Note: max_output_tokens=8192 to ensure complete JSON responses with "thinking" models
        llm_request = LlmRequest(
            model=llm.model,
            contents=[adk_types.Content(role="user", parts=[adk_types.Part(text=query_prompt)])],
            config=adk_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,
                max_output_tokens=8192
            )
        )
        
        # Call LLM
        if hasattr(llm, 'generate_content_async'):
            async for response_event in llm.generate_content_async(llm_request):
                response = response_event
                break
        else:
            response = llm.generate_content(request=llm_request)
        
        # Extract text from response using helper function
        response_text = _extract_text_from_llm_response(response, log_identifier)
        if not response_text or not response_text.strip():
            return [research_question]
        
        log.debug("%s LLM response text (first 200 chars): %s", log_identifier, response_text[:200])
        
        # Parse JSON using helper function with fallback key
        query_data = _parse_json_from_llm_response(response_text, log_identifier, fallback_key="queries")
        if query_data is None:
            return [research_question]
        
        queries = query_data.get("queries", [research_question])[:5]
        
        log.info("%s Generated %d queries via LLM", log_identifier, len(queries))
        return queries
        
    except Exception as e:
        log.error("%s LLM query generation failed: %s, using fallback", log_identifier, str(e), exc_info=True)
        return [research_question]


async def _generate_research_title(
    research_question: str,
    tool_context: ToolContext,
    tool_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a concise, human-readable title for the research using LLM.
    
    The LLM converts the research question into a short, descriptive title
    suitable for display in the UI.
    
    Args:
        research_question: The original research question
        tool_context: Tool context for accessing agent
        tool_config: Optional tool configuration
    
    Returns:
        A concise title string (typically 5-10 words)
    """
    log_identifier = "[DeepResearch:TitleGen]"
    
    try:
        # Get phase-specific or default model (use query_generation model for efficiency)
        llm = _get_model_for_phase("query_generation", tool_context, tool_config)
        
        title_prompt = f"""Generate a concise, human-readable title for this research topic.

Research Question: {research_question}

Requirements:
1. The title should be 5-10 words maximum
2. It should capture the essence of the research topic
3. It should be suitable for display as a heading
4. Do NOT include quotes around the title
5. Do NOT include "Research:" or similar prefixes

Respond with ONLY the title, nothing else."""

        # Note: max_output_tokens=2048 to ensure complete responses with "thinking" models
        llm_request = LlmRequest(
            model=llm.model,
            contents=[adk_types.Content(role="user", parts=[adk_types.Part(text=title_prompt)])],
            config=adk_types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=2048
            )
        )
        
        # Call LLM
        response = None
        if hasattr(llm, 'generate_content_async'):
            async for response_event in llm.generate_content_async(llm_request):
                response = response_event
                break
        else:
            response = llm.generate_content(request=llm_request)
        
        # Extract text from response using helper function
        response_text = _extract_text_from_llm_response(response, log_identifier)
        
        # Clean up the title
        title = response_text.strip().strip('"').strip("'")
        
        # Fallback if title is too long or empty
        if not title or len(title) > 100:
            # Use first 60 chars of research question as fallback
            title = research_question[:60] + "..." if len(research_question) > 60 else research_question
        
        log.info("%s Generated title: '%s'", log_identifier, title)
        return title
        
    except Exception as e:
        log.error("%s LLM title generation failed: %s, using fallback", log_identifier, str(e))
        # Fallback: use truncated research question
        return research_question[:60] + "..." if len(research_question) > 60 else research_question


def _prepare_findings_summary(findings: List[SearchResult], max_findings: int = 20) -> str:
    """Prepare a concise summary of findings for LLM reflection"""
    if not findings:
        return "No findings yet."
    
    # Group by source type
    by_type = {}
    for finding in findings:
        if finding.source_type not in by_type:
            by_type[finding.source_type] = []
        by_type[finding.source_type].append(finding)
    
    summary_parts = []
    summary_parts.append(f"Total Sources: {len(findings)}")
    summary_parts.append(f"Source Types: {', '.join(by_type.keys())}")
    summary_parts.append("")
    
    # Add top findings from each source type
    for source_type, type_findings in by_type.items():
        summary_parts.append(f"{source_type.upper()} Sources ({len(type_findings)}):")
        
        # Show top 5 from each type
        for i, finding in enumerate(sorted(type_findings, key=lambda x: x.relevance_score, reverse=True)[:5], 1):
            title = finding.title[:80] + "..." if len(finding.title) > 80 else finding.title
            content = finding.content[:150] + "..." if len(finding.content) > 150 else finding.content
            summary_parts.append(f"  {i}. {title}")
            summary_parts.append(f"     {content}")
            summary_parts.append(f"     Relevance: {finding.relevance_score:.2f}")
        summary_parts.append("")
    
    return "\n".join(summary_parts)


async def _reflect_on_findings(
    research_question: str,
    findings: List[SearchResult],
    iteration: int,
    tool_context: ToolContext,
    max_iterations: int = 10,
    tool_config: Optional[Dict[str, Any]] = None
) -> ReflectionResult:
    """
    Reflect on current findings using LLM to determine next steps.
    
    The LLM analyzes the research findings to:
    1. Assess information completeness and quality
    2. Identify knowledge gaps
    3. Determine if more research is needed
    4. Generate refined search queries
    
    Supports phase-specific model via tool_config.
    """
    log_identifier = "[DeepResearch:Reflection]"
    
    try:
        # Get phase-specific or default model
        llm = _get_model_for_phase("reflection", tool_context, tool_config)
        
        # Prepare findings summary for LLM
        findings_summary = _prepare_findings_summary(findings)
        
        # Create reflection prompt
        reflection_prompt = f"""You are a research quality analyst. Analyze the current research findings and provide guidance for the next research iteration.

Research Question: {research_question}

Current Iteration: {iteration}

Findings Summary:
{findings_summary}

Please analyze these findings and provide:

1. **Quality Score** (0.0 to 1.0): How complete and comprehensive is the current research?
   - 0.0-0.3: Very incomplete, major gaps
   - 0.4-0.6: Partial coverage, significant gaps remain
   - 0.7-0.8: Good coverage, minor gaps
   - 0.9-1.0: Comprehensive, excellent coverage

2. **Knowledge Gaps**: What important aspects are missing or under-covered?

3. **Should Continue**: Should we conduct another research iteration? (yes/no)
   - Consider: quality score, iteration number, diminishing returns
   - Maximum iterations allowed: {max_iterations}

4. **Suggested Queries**: If continuing, what 3-5 specific search queries would fill the gaps?

Respond in JSON format:
{{
  "quality_score": 0.0-1.0,
  "gaps": ["gap1", "gap2", ...],
  "should_continue": true/false,
  "suggested_queries": ["query1", "query2", ...],
  "reasoning": "Brief explanation of your assessment"
}}"""

        log.info("%s Calling LLM for reflection analysis", log_identifier)
        
        # Create LLM request
        # Note: max_output_tokens=8192 to ensure complete JSON responses with "thinking" models
        llm_request = LlmRequest(
            model=llm.model,
            contents=[adk_types.Content(role="user", parts=[adk_types.Part(text=reflection_prompt)])],
            config=adk_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
                max_output_tokens=8192
            )
        )
        
        # Call LLM
        if hasattr(llm, 'generate_content_async'):
            async for response_event in llm.generate_content_async(llm_request):
                response = response_event
                break
        else:
            response = llm.generate_content(request=llm_request)
        
        # Extract text from response using helper function
        response_text = _extract_text_from_llm_response(response, log_identifier)
        if not response_text or not response_text.strip():
            log.warning("%s LLM returned empty response for reflection", log_identifier)
            # Continue research if we have few findings
            should_continue = len(findings) < 15 and iteration < 3
            return ReflectionResult(
                quality_score=0.6,
                gaps=["Need more sources"],
                should_continue=should_continue,
                suggested_queries=[f"{research_question} detailed analysis", f"{research_question} comprehensive overview"],
                reasoning="LLM returned empty response, using fallback logic"
            )
        
        # Parse JSON using helper function
        reflection_data = _parse_json_from_llm_response(response_text, log_identifier, fallback_key="quality_score")
        if reflection_data is None:
            should_continue = len(findings) < 15 and iteration < 3
            return ReflectionResult(
                quality_score=0.6,
                gaps=["Need more sources"],
                should_continue=should_continue,
                suggested_queries=[f"{research_question} comprehensive", f"{research_question} detailed"],
                reasoning="Could not parse LLM response, using fallback"
            )
        
        quality_score = float(reflection_data.get("quality_score", 0.5))
        gaps = reflection_data.get("gaps", [])
        should_continue = reflection_data.get("should_continue", False) and iteration < max_iterations
        suggested_queries = reflection_data.get("suggested_queries", [])
        reasoning = reflection_data.get("reasoning", "LLM reflection completed")
        
        log.info("%s LLM Reflection - Quality: %.2f, Continue: %s",
                log_identifier, quality_score, should_continue)
        log.info("%s Reasoning: %s", log_identifier, reasoning)
        
        return ReflectionResult(
            quality_score=quality_score,
            gaps=gaps,
            should_continue=should_continue,
            suggested_queries=suggested_queries[:5] if suggested_queries else [research_question],
            reasoning=reasoning
        )
        
    except Exception as e:
        log.error("%s LLM reflection failed: %s", log_identifier, str(e))
        # Fallback: continue if we don't have many findings yet
        should_continue = len(findings) < 15 and iteration < 3
        return ReflectionResult(
            quality_score=0.5,
            gaps=["LLM reflection error"],
            should_continue=should_continue,
            suggested_queries=[f"{research_question} overview"] if should_continue else [],
            reasoning=f"Error during reflection: {str(e)}"
        )


async def _select_sources_to_fetch(
    research_question: str,
    findings: List[SearchResult],
    max_to_fetch: int,
    tool_context: ToolContext,
    tool_config: Optional[Dict[str, Any]] = None
) -> List[SearchResult]:
    """
    Use LLM to intelligently select which sources to fetch based on quality and relevance.
    
    Supports phase-specific model via tool_config.
    """
    log_identifier = "[DeepResearch:SelectSources]"
    
    try:
        # Get phase-specific or default model
        llm = _get_model_for_phase("source_selection", tool_context, tool_config)
        
        # Prepare source list for LLM - only web sources can be fetched for full content
        web_findings = [f for f in findings if f.source_type == "web" and f.url]
        if not web_findings:
            return []
        
        sources_summary = []
        for i, finding in enumerate(web_findings[:20], 1):  # Limit to top 20 for LLM
            sources_summary.append(f"{i}. {finding.title}")
            sources_summary.append(f"   URL: {finding.url}")
            sources_summary.append(f"   Snippet: {finding.content[:150]}...")
            sources_summary.append(f"   Relevance: {finding.relevance_score:.2f}")
            sources_summary.append("")
        
        selection_prompt = f"""You are a research quality analyst. Select the {max_to_fetch} BEST sources to fetch full content from for this research question:

Research Question: {research_question}

Available Sources:
{chr(10).join(sources_summary)}

Select the {max_to_fetch} sources that are most likely to provide:
1. Authoritative, credible information (e.g., .edu, .gov, established organizations)
2. Comprehensive coverage of the topic
3. Unique perspectives or data
4. Academic or expert analysis

You MUST respond with ONLY valid JSON in this exact format:
{{
  "selected_sources": [1, 3, 5],
  "reasoning": "Brief explanation"
}}

Do not include any other text, markdown formatting, or explanations outside the JSON."""

        # Note: max_output_tokens=8192 to ensure complete JSON responses with "thinking" models
        llm_request = LlmRequest(
            model=llm.model,
            contents=[adk_types.Content(role="user", parts=[adk_types.Part(text=selection_prompt)])],
            config=adk_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
                max_output_tokens=8192
            )
        )
        
        if hasattr(llm, 'generate_content_async'):
            async for response_event in llm.generate_content_async(llm_request):
                response = response_event
                break
        else:
            response = llm.generate_content(request=llm_request)
        
        # Extract text from response using helper function
        response_text = _extract_text_from_llm_response(response, log_identifier)
        if not response_text or not response_text.strip():
            log.warning("%s LLM returned empty response, using fallback selection", log_identifier)
            web_findings = [f for f in findings if f.source_type == "web" and f.url]
            return sorted(web_findings, key=lambda x: x.relevance_score, reverse=True)[:max_to_fetch]
        
        log.debug("%s LLM response text: %s", log_identifier, response_text[:200])
        
        # Parse JSON using helper function
        selection_data = _parse_json_from_llm_response(response_text, log_identifier, fallback_key="selected_sources")
        if selection_data is None:
            log.warning("%s Failed to parse JSON, using fallback selection", log_identifier)
            web_findings = [f for f in findings if f.source_type == "web" and f.url]
            return sorted(web_findings, key=lambda x: x.relevance_score, reverse=True)[:max_to_fetch]
        
        selected_indices = selection_data.get("selected_sources", [])
        reasoning = selection_data.get("reasoning", "")
        
        if not selected_indices:
            log.warning("%s LLM returned empty selection, using fallback", log_identifier)
            web_findings = [f for f in findings if f.source_type == "web" and f.url]
            return sorted(web_findings, key=lambda x: x.relevance_score, reverse=True)[:max_to_fetch]
        
        log.info("%s LLM selected %d sources: %s", log_identifier, len(selected_indices), reasoning)
        
        # Convert 1-based indices to actual findings
        # Handle case where LLM returns strings instead of integers
        selected_sources = []
        for idx in selected_indices:
            try:
                idx_int = int(idx)  # Convert to int in case LLM returned strings
                if 1 <= idx_int <= len(web_findings):
                    selected_sources.append(web_findings[idx_int - 1])
            except (ValueError, TypeError):
                log.warning("%s Invalid index value: %s (type: %s), skipping", log_identifier, idx, type(idx).__name__)
                continue
        
        return selected_sources[:max_to_fetch]
        
    except Exception as e:
        log.error("%s LLM source selection failed: %s, using fallback", log_identifier, str(e), exc_info=True)
        web_findings = [f for f in findings if f.source_type == "web" and f.url]
        return sorted(web_findings, key=lambda x: x.relevance_score, reverse=True)[:max_to_fetch]


async def _fetch_selected_sources(
    selected_sources: List[SearchResult],
    tool_context: ToolContext,
    tool_config: Optional[Dict[str, Any]],
    citation_tracker: ResearchCitationTracker,
    start_time: float = 0,
    max_runtime_seconds: Optional[int] = None
) -> Dict[str, int]:
    """Fetch full content from LLM-selected sources and return success/failure stats"""
    log_identifier = "[DeepResearch:FetchSources]"
    
    if not selected_sources:
        log.info("%s No sources selected to fetch", log_identifier)
        return {"success": 0, "failed": 0}
    
    log.info("%s Fetching full content from %d selected sources", log_identifier, len(selected_sources))
    
    # Fetch sources in parallel with progress updates
    fetch_tasks = []
    for i, source in enumerate(selected_sources, 1):
        # Prepare current URL being fetched for structured progress
        current_url_info = {
            "url": source.url,
            "title": source.title,
            "favicon": f"https://www.google.com/s2/favicons?domain={source.url}&sz=32" if source.url else ""
        }
        
        # Send progress for each source being fetched with phase info
        await _send_research_progress(
            f"Reading content from: {source.title[:50]}... ({i}/{len(selected_sources)})",
            tool_context,
            phase="analyzing"
        )
        fetch_tasks.append(web_request(
            url=source.url,
            method="GET",
            tool_context=tool_context,
            tool_config=tool_config
        ))
    
    results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
    
    # Track success/failure stats
    success_count = 0
    failed_count = 0
    
    # Update findings with fetched content
    for source, result in zip(selected_sources, results):
        if isinstance(result, dict) and result.get("status") == "success":
            # Extract preview from result
            preview = result.get("result_preview", "")
            if preview:
                # Append fetched content to existing snippet
                source.content = f"{source.content}\n\n[Full Content Fetched]\n{preview}"
                source.metadata["fetched"] = True
                source.metadata["fetch_status"] = "success"
                success_count += 1
                log.info("%s Successfully fetched content from %s", log_identifier, source.url)
                
                # Update citation tracker with fetched metadata
                citation_tracker.update_citation_after_fetch(source)
            else:
                source.metadata["fetched"] = False
                source.metadata["fetch_error"] = "No content in response"
                failed_count += 1
                log.warning("%s No content returned from %s", log_identifier, source.url)
        elif isinstance(result, Exception):
            log.warning("%s Failed to fetch %s: %s", log_identifier, source.url, str(result))
            source.metadata["fetched"] = False
            source.metadata["fetch_error"] = str(result)
            failed_count += 1
        else:
            error_msg = result.get("message", "Unknown error") if isinstance(result, dict) else "Unknown error"
            log.warning("%s Failed to fetch %s: %s", log_identifier, source.url, error_msg)
            source.metadata["fetched"] = False
            source.metadata["fetch_error"] = error_msg
            failed_count += 1
    
    # Log summary
    log.info("%s Fetch complete: %d succeeded, %d failed out of %d total",
             log_identifier, success_count, failed_count, len(selected_sources))
    
    # Send summary progress update
    if failed_count > 0:
        await _send_research_progress(
            f"Content fetched: {success_count} succeeded, {failed_count} failed",
            tool_context,
            phase="analyzing"
        )
    
    return {"success": success_count, "failed": failed_count}


def _prepare_findings_for_report(findings: List[SearchResult], max_findings: int = 30) -> str:
    """Prepare findings text for LLM report generation with enhanced content"""
    sorted_findings = sorted(findings, key=lambda x: x.relevance_score, reverse=True)[:max_findings]
    
    findings_text = []
    findings_text.append("# Research Findings\n")
    
    # Group findings by whether they have full content
    fetched_findings = [f for f in sorted_findings if f.metadata.get('fetched')]
    snippet_findings = [f for f in sorted_findings if not f.metadata.get('fetched')]
    
    # Prioritize fetched content (full articles)
    if fetched_findings:
        findings_text.append("## Detailed Sources (Full Content Retrieved)\n")
        for finding in fetched_findings[:15]:  # Top 15 fetched sources
            findings_text.append(f"\n### {finding.title}")
            findings_text.append(f"**Citation ID:** {finding.citation_id}")
            findings_text.append(f"**URL:** {finding.url or 'N/A'}")
            findings_text.append(f"**Relevance:** {finding.relevance_score:.2f}\n")
            
            # Include substantial content from fetched sources (up to 5000 chars for comprehensive analysis)
            content_to_include = finding.content[:5000] if len(finding.content) > 5000 else finding.content
            if len(finding.content) > 5000:
                content_to_include += "\n\n[Content continues but truncated for length...]"
            findings_text.append(f"**Content:**\n{content_to_include}\n")
            findings_text.append("---\n")
    
    # Add snippet-only sources
    if snippet_findings:
        findings_text.append("\n## Additional Sources (Snippets)\n")
        for finding in snippet_findings[:15]:  # Top 15 snippet sources
            findings_text.append(f"\n### {finding.title}")
            findings_text.append(f"**Citation ID:** {finding.citation_id}")
            findings_text.append(f"**URL:** {finding.url or 'N/A'}")
            findings_text.append(f"**Snippet:** {finding.content}")
            findings_text.append(f"**Relevance:** {finding.relevance_score:.2f}\n")
            findings_text.append("---\n")
    
    return "\n".join(findings_text)


def _generate_sources_section(all_findings: List[SearchResult]) -> str:
    """Generate references section with ALL cited sources (both fetched and snippet-only)"""
    # Include ALL sources that have citation IDs (all findings that were cited)
    cited_sources = [f for f in all_findings if f.citation_id]
    
    if not cited_sources:
        return ""
    
    # Separate fetched vs snippet-only for better organization
    fetched_sources = [f for f in cited_sources if f.metadata.get('fetched')]
    snippet_sources = [f for f in cited_sources if not f.metadata.get('fetched')]
    
    section = "\n\n---\n\n## References\n\n"
    
    # Group by source type
    web_sources = [f for f in cited_sources if f.source_type == "web"]
    kb_sources = [f for f in cited_sources if f.source_type == "kb"]
    
    if web_sources:
        for i, source in enumerate(web_sources, 1):
            if source.citation_id and source.url:
                # Extract citation number from citation_id (e.g., "research0" -> 0)
                citation_num = int(source.citation_id.replace("research", "").replace("file", "").replace("ref", ""))
                display_num = citation_num + 1  # Convert 0-based to 1-based for display
                
                # DEBUG: Log citation mapping
                log.info("[DeepResearch:References] Mapping citation_id=%s to reference number [%d]", source.citation_id, display_num)
                
                # Indicate if this was read in full or just a snippet
                fetch_indicator = " *(read in full)*" if source.metadata.get('fetched') else " *(search result)*"
                section += f"**[{display_num}]** {source.title}{fetch_indicator}  \n{source.url}\n\n"
    
    if kb_sources:
        for source in kb_sources:
            if source.citation_id:
                # Extract citation number from citation_id
                citation_num = int(source.citation_id.replace("research", "").replace("file", "").replace("ref", ""))
                display_num = citation_num + 1  # Convert 0-based to 1-based for display
                
                fetch_indicator = " *(read in full)*" if source.metadata.get('fetched') else " *(search result)*"
                section += f"**[{display_num}]** {source.title}{fetch_indicator}\n\n"
    
    return section


def _generate_methodology_section(all_findings: List[SearchResult]) -> str:
    """Generate research methodology section with statistics"""
    web_sources = [f for f in all_findings if f.source_type == "web"]
    kb_sources = [f for f in all_findings if f.source_type == "kb"]
    
    # Count fetched vs snippet-only sources
    fetched_sources = [f for f in all_findings if f.metadata.get('fetched')]
    snippet_sources = [f for f in all_findings if not f.metadata.get('fetched')]
    
    section = "## Research Methodology\n\n"
    section += f"This research analyzed **{len(all_findings)} sources** across multiple iterations:\n\n"
    section += f"- **{len(fetched_sources)} sources** were read in full detail (cited in References above)\n"
    section += f"- **{len(snippet_sources)} additional sources** were consulted via search snippets\n"
    section += f"- Source types: {len(web_sources)} web, {len(kb_sources)} knowledge base\n\n"
    section += "The research process involved:\n"
    section += "1. Generating targeted search queries using AI\n"
    section += "2. Searching across multiple information sources\n"
    section += "3. Selecting the most authoritative and relevant sources\n"
    section += "4. Retrieving and analyzing full content from selected sources\n"
    section += "5. Synthesizing findings into a comprehensive report\n"
    
    return section


async def _generate_research_report(
    research_question: str,
    all_findings: List[SearchResult],
    citation_tracker: ResearchCitationTracker,
    tool_context: ToolContext,
    tool_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate comprehensive research report using LLM.
    The LLM synthesizes findings into a coherent narrative with proper citations.
    
    Supports phase-specific model via tool_config.
    """
    log_identifier = "[DeepResearch:ReportGen]"
    log.info("%s Generating report from %d findings", log_identifier, len(all_findings))
    
    try:
        # Get phase-specific or default model
        llm = _get_model_for_phase("report_generation", tool_context, tool_config)
        
        # Prepare findings for LLM
        findings_text = _prepare_findings_for_report(all_findings)
        
        # Create report generation prompt - emphasizing synthesis over copying
        report_prompt = f"""You are an expert research analyst. Your task is to SYNTHESIZE information from multiple sources into an original, comprehensive research report.

Research Question: {research_question}

You have access to {len(all_findings)} sources below. Your job is to READ ALL OF THEM, extract key information, and create a well-written report.

Source Materials:
{findings_text}

CRITICAL INSTRUCTIONS:

⚠️ DO NOT COPY: You must NOT copy text directly from any single source. You must SYNTHESIZE information from MULTIPLE sources.

⚠️ ORIGINAL WRITING: Write in your own words, combining insights from different sources.

⚠️ DO NOT INCLUDE WORD COUNTS: Do NOT include word count targets (like "300-500 words") in your section headings or anywhere in the output. These are internal guidelines for you only.

REPORT STRUCTURE GUIDELINES (aim for 3000-5000 words total, but DO NOT mention word counts in output):

Write the following sections WITHOUT including word count targets in headings:

## Executive Summary
Synthesize the MOST IMPORTANT insights from ALL sources. Highlight key findings that answer the research question. Provide context for why this topic matters. DO NOT copy from any single source.

## Introduction
Explain the research question and its significance. Provide historical or contextual background. Outline what the report will cover. Draw context from multiple sources [[cite:researchX]].

## Main Analysis
Organize into 5-8 thematic sections with descriptive headings (###). For EACH section:
- Create a descriptive heading like "### Historical Development" or "### Economic Impact" (NO word counts)
- Draw information from multiple sources
- Start each paragraph with a topic sentence
- Support claims with citations from different sources.[[cite:researchX]][[cite:researchY]]
- Explain implications and connections
- Compare and contrast different perspectives
- NEVER copy paragraphs from a single source

## Comparative Analysis
Compare different perspectives across sources. Identify agreements and contradictions. Analyze why sources might differ. Synthesize a balanced view. Cite multiple sources for each point.

## Implications
Discuss practical implications. Identify applications or consequences. Suggest areas needing further research. Draw from multiple sources.

## Conclusion
Synthesize the key takeaways from ALL sources. Provide final analytical insights. Suggest future directions.

⚠️ DO NOT CREATE A REFERENCES SECTION: The system will automatically append a properly formatted References section with all cited sources. Your report should end with the Conclusion section.

CITATION RULES:
- Use [[cite:researchN]] format where N is the citation number from sources above
- Place citations AFTER the period at the end of sentences (e.g., "This is a fact.[[cite:research0]]")
- Use multiple citations when multiple sources support a point: .[[cite:research0]][[cite:research2]]
- Cite sources even when paraphrasing

QUALITY CHECKS:
✓ Have I synthesized from MULTIPLE sources (not just one)?
✓ Have I written in my OWN words (not copied)?
✓ Have I cited ALL factual claims?
✓ Have I organized information thematically (not source-by-source)?
✓ Have I avoided including word count targets in my output?

Write your research report now. Format in Markdown. Remember: NO word counts in section headings or anywhere in the output.
"""

        log.info("%s Calling LLM for report generation", log_identifier)
        
        # Create LLM request with reasonable max tokens for faster generation
        # Reduced from 32000 to 8000 for better performance while still allowing comprehensive reports
        llm_request = LlmRequest(
            model=llm.model,
            contents=[adk_types.Content(role="user", parts=[adk_types.Part(text=report_prompt)])],
            config=adk_types.GenerateContentConfig(
                temperature=1.0,
                max_output_tokens=8000  # Reduced from 32000 for faster generation
            )
        )
        
        # Call LLM with streaming and progress updates
        report_body = ""
        response_count = 0
        last_progress_update = 0
        import time as time_module
        stream_start_time = time_module.time()
        
        try:
            # IMPORTANT: Pass stream=True to enable streaming mode
            # Without this, the LLM call waits for the entire response before yielding,
            # which can cause timeouts with large prompts or slow models
            #
            # NOTE: LiteLlm streaming yields:
            # 1. Multiple partial responses (is_partial=True) with delta text chunks
            # 2. One final aggregated response (is_partial=False) with the FULL accumulated text
            #
            # We ONLY process partial responses to avoid duplication. The final aggregated
            # response contains the same text we've already accumulated from the partials.
            async for response_event in llm.generate_content_async(llm_request, stream=True):
                response_count += 1
                
                # Check if this is a partial (streaming chunk) or final (aggregated) response
                # LiteLlm sets partial=True for streaming chunks, partial=False for final
                is_partial = getattr(response_event, 'partial', None)
                
                # Skip non-partial (final aggregated) responses - they contain duplicate content
                # The final response has the full accumulated text which we've already collected
                if is_partial is False:
                    continue
                
                # Try different extraction methods
                extracted_text = ""
                if hasattr(response_event, 'text') and response_event.text:
                    extracted_text = response_event.text
                elif hasattr(response_event, 'parts') and response_event.parts:
                    extracted_text = "".join([part.text for part in response_event.parts if hasattr(part, 'text') and part.text])
                elif hasattr(response_event, 'content') and response_event.content:
                    if hasattr(response_event.content, 'parts') and response_event.content.parts:
                        extracted_text = "".join([part.text for part in response_event.content.parts if hasattr(part, 'text') and part.text])
                
                if extracted_text:
                    # For partial responses, always append (they are delta chunks)
                    report_body += extracted_text
                    
                    # Send progress update every 500 characters to show activity and reset peer timeout
                    if len(report_body) - last_progress_update >= 500:
                        last_progress_update = len(report_body)
                        progress_pct = min(95, 85 + int((len(report_body) / 3000) * 10))  # 85-95%
                        
                        # Send progress update to reset orchestrator's peer timeout
                        await _send_research_progress(
                            f"Writing report... ({len(report_body)} characters)",
                            tool_context,
                            phase="writing",
                            progress_percentage=progress_pct,
                            sources_found=len(all_findings)
                        )
            
            log.info("%s Report generation complete: %d chars", log_identifier, len(report_body))
                
        except Exception as stream_error:
            log.error("%s Error during LLM streaming: %s", log_identifier, str(stream_error))
            raise
        
        # Add sources section
        sources_section = _generate_sources_section(all_findings)
        report_body += "\n\n" + sources_section
        
        # Add methodology section
        methodology_section = _generate_methodology_section(all_findings)
        report_body += "\n\n" + methodology_section
        
        return report_body
        
    except Exception as e:
        log.error("%s LLM report generation failed: %s", log_identifier, str(e))
        return f"# Research Report: {research_question}\n\nError generating report: {str(e)}"


async def deep_research(
    research_question: str,
    research_type: str = "quick",
    sources: Optional[List[str]] = None,
    max_iterations: Optional[int] = None,
    max_sources_per_iteration: int = 5,
    kb_ids: Optional[List[str]] = None,
    max_runtime_minutes: Optional[int] = None,
    max_runtime_seconds: Optional[int] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Performs comprehensive, iterative research across multiple sources.
    
    Configuration Priority (highest to lowest):
    1. Explicit parameters (max_iterations, max_runtime_minutes/max_runtime_seconds)
    2. Tool config (tool_config.max_iterations, tool_config.max_runtime_seconds)
    3. Research type translation ("quick" or "in-depth")
    
    Args:
        research_question: The research question or topic to investigate
        research_type: Type of research - "quick" (5min, 3 iter) or "in-depth" (10min, 10 iter)
        sources: Sources to search (default from tool_config or ["web"])
        max_iterations: Maximum research iterations (overrides tool_config and research_type)
        max_sources_per_iteration: Max results per source per iteration (default: 5)
        kb_ids: Specific knowledge base IDs to search
        max_runtime_minutes: Maximum runtime in minutes (1-10). Converted to seconds internally.
        max_runtime_seconds: Maximum runtime in seconds (60-600). Overrides tool_config and research_type.
        tool_context: ADK tool context
        tool_config: Tool configuration with optional max_iterations, max_runtime_seconds, sources
    
    Returns:
        Dictionary with research report and metadata
    """
    log_identifier = "[DeepResearch]"
    log.info("%s Starting deep research: %s", log_identifier, research_question)
    
    # Resolve configuration with priority: explicit params > tool_config > research_type
    config = tool_config or {}
    
    # Resolve max_iterations
    if max_iterations is None:
        max_iterations = config.get("max_iterations")
        if max_iterations is not None:
            log.info("%s Using max_iterations from tool_config: %d", log_identifier, max_iterations)
        else:
            # Fallback to research_type translation
            if research_type.lower() in ["in-depth", "indepth", "in_depth", "deep", "comprehensive"]:
                max_iterations = 10
                log.info("%s Using max_iterations from research_type 'in-depth': %d", log_identifier, max_iterations)
            else:
                max_iterations = 3
                log.info("%s Using max_iterations from research_type 'quick': %d", log_identifier, max_iterations)
    else:
        log.info("%s Using explicit max_iterations parameter: %d", log_identifier, max_iterations)
    
    # Resolve max_runtime_seconds (with priority: max_runtime_minutes > max_runtime_seconds > tool_config > research_type)
    # First, check if max_runtime_minutes was provided (LLM-friendly parameter)
    if max_runtime_minutes is not None:
        max_runtime_seconds = max_runtime_minutes * 60
        log.info("%s Using explicit max_runtime_minutes parameter: %d minutes (%d seconds)",
                log_identifier, max_runtime_minutes, max_runtime_seconds)
    elif max_runtime_seconds is not None:
        log.info("%s Using explicit max_runtime_seconds parameter: %d", log_identifier, max_runtime_seconds)
    else:
        # Check tool_config (support both seconds and minutes)
        config_duration = config.get("max_runtime_seconds") or config.get("duration_seconds")
        config_duration_minutes = config.get("duration_minutes")
        
        if config_duration is not None:
            max_runtime_seconds = config_duration
            log.info("%s Using max_runtime_seconds from tool_config: %d", log_identifier, max_runtime_seconds)
        elif config_duration_minutes is not None:
            max_runtime_seconds = config_duration_minutes * 60
            log.info("%s Using duration_minutes from tool_config: %d minutes (%d seconds)",
                    log_identifier, config_duration_minutes, max_runtime_seconds)
        else:
            # Fallback to research_type translation
            if research_type.lower() in ["in-depth", "indepth", "in_depth", "deep", "comprehensive"]:
                max_runtime_seconds = 600  # 10 minutes
                log.info("%s Using max_runtime_seconds from research_type 'in-depth': %d seconds",
                        log_identifier, max_runtime_seconds)
            else:
                max_runtime_seconds = 300  # 5 minutes
                log.info("%s Using max_runtime_seconds from research_type 'quick': %d seconds",
                        log_identifier, max_runtime_seconds)
    
    # Resolve sources
    if sources is None:
        sources = config.get("sources", ["web"])
        log.info("%s Using sources from config: %s", log_identifier, sources)
    
    if not tool_context:
        return {"status": "error", "message": "ToolContext is missing"}
    
    # Default sources - web only
    if sources is None:
        sources = ["web"]
    
    # Track start time for runtime limit
    import time
    start_time = time.time()
    
    # Validate and filter sources
    if sources:
        # Validate and filter sources - only allow web and kb
        allowed_sources = {"web", "kb"}
        sources = [s for s in sources if s in allowed_sources]
        
        # If no valid sources after filtering, use default
        if not sources:
            log.warning("%s No valid sources provided, using default: ['web']", log_identifier)
            sources = ["web"]
        else:
            log.info("%s Using validated sources: %s", log_identifier, sources)
    
    # Validate iterations and runtime
    max_iterations = max(1, min(max_iterations, 10))
    if max_runtime_seconds:
        max_runtime_seconds = max(60, min(max_runtime_seconds, 600))  # 1-10 minutes
        log.info("%s Runtime limit set to %d seconds", log_identifier, max_runtime_seconds)
    
    try:
        # Initialize citation tracker
        citation_tracker = ResearchCitationTracker(research_question)
        
        # Send initial progress with structured data
        await _send_research_progress(
            "Planning research strategy and generating search queries...",
            tool_context,
            phase="planning",
            progress_percentage=5,
            current_iteration=0,
            total_iterations=max_iterations,
            sources_found=0,
            elapsed_seconds=int(time.time() - start_time),
            max_runtime_seconds=max_runtime_seconds or 0
        )
        
        # Generate initial queries using LLM (with phase-specific model support)
        queries = await _generate_initial_queries(research_question, tool_context, tool_config)
        log.info("%s Generated %d initial queries", log_identifier, len(queries))
        
        # Generate human-readable title for the research using LLM
        log.info("%s Generating LLM title for research question: %s", log_identifier, research_question[:100])
        research_title = await _generate_research_title(research_question, tool_context, tool_config)
        citation_tracker.set_title(research_title)
        log.info("%s LLM-generated research title: '%s' (original query: '%s')",
                log_identifier, research_title, research_question[:50])
        
        # Send initial RAG info update with title (no sources yet)
        # This allows the UI to display the title in the RAG info panel immediately
        await _send_rag_info_update(citation_tracker, tool_context, is_complete=False)
        
        # Iterative research loop
        all_findings: List[SearchResult] = []
        seen_sources_global = set()  # Track seen sources across ALL iterations
        
        for iteration in range(1, max_iterations + 1):
            # Check runtime limit - only applies to research iterations, not report generation
            if max_runtime_seconds:
                elapsed = time.time() - start_time
                if elapsed >= max_runtime_seconds:
                    log.info("%s Runtime limit reached (%d seconds), stopping research iterations. Will proceed to generate report from %d sources.",
                            log_identifier, max_runtime_seconds, len(all_findings))
                    await _send_research_progress(
                        f"Research time limit reached ({int(elapsed)}s). Proceeding to generate report from {len(all_findings)} sources...",
                        tool_context,
                        phase="writing",
                        progress_percentage=80,
                        current_iteration=iteration,
                        total_iterations=max_iterations,
                        sources_found=len(all_findings),
                        elapsed_seconds=int(elapsed),
                        max_runtime_seconds=max_runtime_seconds
                    )
                    break
            
            log.info("%s === Iteration %d/%d ===", log_identifier, iteration, max_iterations)
            
            # Calculate progress percentage for this iteration
            iteration_progress_base = 10 + ((iteration - 1) / max_iterations) * 70  # 10-80% for iterations
            
            # Search with current queries
            iteration_findings = []
            for query_idx, query in enumerate(queries, 1):
                # Start tracking this query in citation tracker
                citation_tracker.start_query(query)
                
                # Calculate sub-progress within iteration
                query_progress = iteration_progress_base + (query_idx / len(queries)) * (70 / max_iterations) * 0.3
                
                # Send progress for each query with structured data
                await _send_research_progress(
                    f"{query[:60]}...",
                    tool_context,
                    phase="searching",
                    progress_percentage=int(query_progress),
                    current_iteration=iteration,
                    total_iterations=max_iterations,
                    sources_found=len(all_findings),
                    current_query=query,
                    elapsed_seconds=int(time.time() - start_time),
                    max_runtime_seconds=max_runtime_seconds or 0
                )
                results = await _multi_source_search(
                    query, sources, max_sources_per_iteration,
                    kb_ids, tool_context, tool_config
                )
                
                # Deduplicate against ALL previously seen sources (web-only version)
                query_findings = []
                for result in results:
                    # For web sources, use URL or title as unique key
                    key = result.url or f"web:{result.title}"
                    
                    # Only add if not seen before
                    if key not in seen_sources_global:
                        seen_sources_global.add(key)
                        query_findings.append(result)
                        iteration_findings.append(result)
                
                # Add citations for this query's findings
                for finding in query_findings:
                    citation_tracker.add_citation(finding, query)
            
            all_findings.extend(iteration_findings)
            
            log.info("%s Iteration %d found %d new sources (total: %d)",
                    log_identifier, iteration, len(iteration_findings), len(all_findings))
            
            # Send RAG info update with new sources after each iteration
            # This allows the UI to display sources as they are discovered
            if iteration_findings:
                await _send_rag_info_update(citation_tracker, tool_context, is_complete=False)
            
            # Select and fetch full content from best sources in THIS iteration
            # This allows the LLM to reflect on full content, not just snippets
            selection_progress = iteration_progress_base + (70 / max_iterations) * 0.4
            
            # Prepare URL list early for the entire analyzing phase
            fetching_url_list = []
            
            # Select top 2-3 sources from this iteration to fetch/analyze
            sources_to_display_count = min(3, len(all_findings))
            
            # For web sources: select and fetch full content from current iteration (with phase-specific model support)
            selected_sources = []
            if len(iteration_findings) > 0:
                sources_to_fetch_count = min(3, len(iteration_findings))
                selected_sources = await _select_sources_to_fetch(
                    research_question, iteration_findings, max_to_fetch=sources_to_fetch_count,
                    tool_context=tool_context, tool_config=tool_config
                )
            
            # Prepare display list for UI - show ONLY NEW sources being analyzed (not duplicates)
            # Use iteration_findings which contains only NEW sources after deduplication
            if selected_sources:
                # Web sources that will be fetched (only new ones)
                fetching_url_list = [
                    {
                        "url": src.url,
                        "title": src.title,
                        "favicon": f"https://www.google.com/s2/favicons?domain={src.url}&sz=32" if src.url else "",
                        "source_type": src.source_type
                    }
                    for src in selected_sources
                ]
            else:
                # Web-only version - no other sources to display
                fetching_url_list = []
            
            # Start unified "analyzing" phase - covers selecting, fetching, and analyzing
            # Skip if no sources found
            if len(all_findings) > 0:
                analyze_progress = iteration_progress_base + (70 / max_iterations) * 0.4
                await _send_research_progress(
                    f"Analyzing {len(all_findings)} sources (reading {len(fetching_url_list)} in detail)...",
                    tool_context,
                    phase="analyzing",
                    progress_percentage=int(analyze_progress),
                    current_iteration=iteration,
                    total_iterations=max_iterations,
                    sources_found=len(all_findings),
                    fetching_urls=fetching_url_list,
                    elapsed_seconds=int(time.time() - start_time),
                    max_runtime_seconds=max_runtime_seconds or 0
                )
            
            # Fetch selected sources (still within analyzing phase) - only for web sources
            if selected_sources:
                fetch_stats = await _fetch_selected_sources(selected_sources, tool_context, tool_config, citation_tracker, start_time, max_runtime_seconds)
                log.info("%s Iteration %d fetch stats: %s", log_identifier, iteration, fetch_stats)
            
            # Continue analyzing phase - reflect on findings
            # Skip if no sources found
            if len(all_findings) > 0:
                reflect_progress = iteration_progress_base + (70 / max_iterations) * 0.9
                await _send_research_progress(
                    f"Analyzing {len(all_findings)} sources and identifying knowledge gaps...",
                    tool_context,
                    phase="analyzing",
                    progress_percentage=int(reflect_progress),
                    current_iteration=iteration,
                    total_iterations=max_iterations,
                    sources_found=len(all_findings),
                    fetching_urls=fetching_url_list,  # Keep URLs visible during reflection
                    elapsed_seconds=int(time.time() - start_time),
                    max_runtime_seconds=max_runtime_seconds or 0
                )
            
            reflection = await _reflect_on_findings(
                research_question, all_findings, iteration, tool_context, max_iterations, tool_config
            )
            
            log.info("%s Reflection: %s", log_identifier, reflection.reasoning)
            
            # Check if we should continue
            if not reflection.should_continue or iteration >= max_iterations:
                log.info("%s Research complete after %d iterations", log_identifier, iteration)
                break
            
            # Generate new queries for next iteration based on reflection
            queries = reflection.suggested_queries
        
        # Generate final report
        await _send_research_progress(
            f"Writing comprehensive research report from {len(all_findings)} sources...",
            tool_context,
            phase="writing",
            progress_percentage=85,
            current_iteration=max_iterations,
            total_iterations=max_iterations,
            sources_found=len(all_findings),
            elapsed_seconds=int(time.time() - start_time),
            max_runtime_seconds=max_runtime_seconds or 0
        )
        
        report = await _generate_research_report(
            research_question, all_findings, citation_tracker, tool_context, tool_config
        )
        
        log.info("%s Research complete: %d total sources, report length: %d chars",
                log_identifier, len(all_findings), len(report))
        
        from ..utils.artifact_helpers import (
            save_artifact_with_metadata,
            decode_and_get_bytes,
            sanitize_to_filename,
        )
        from ..utils.context_helpers import get_original_session_id
        
        # Generate filename from research question using utility function
        artifact_filename = sanitize_to_filename(
            research_question,
            max_length=50,
            suffix="_report.md"
        )
        # Get artifact service from invocation context
        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            log.warning("%s ArtifactService not available, cannot save research report artifact", log_identifier)
            artifact_result = {"status": "error", "message": "ArtifactService not available"}
        else:
            # Prepare content bytes and metadata
            try:
                artifact_bytes, final_mime_type = decode_and_get_bytes(
                    report, "text/markdown", f"{log_identifier}[CreateArtifact]"
                )
            except Exception as decode_error:
                log.error("%s Error preparing artifact bytes: %s", log_identifier, str(decode_error))
                raise
            
            # Get timestamp from session
            session_last_update_time = inv_context.session.last_update_time
            if isinstance(session_last_update_time, datetime):
                timestamp_for_artifact = session_last_update_time
            elif isinstance(session_last_update_time, (int, float)):
                try:
                    timestamp_for_artifact = datetime.fromtimestamp(session_last_update_time, timezone.utc)
                except Exception:
                    timestamp_for_artifact = datetime.now(timezone.utc)
            else:
                timestamp_for_artifact = datetime.now(timezone.utc)
            
            # Save artifact directly using artifact service
            try:
                artifact_result = await save_artifact_with_metadata(
                    artifact_service=artifact_service,
                    app_name=inv_context.app_name,
                    user_id=inv_context.user_id,
                    session_id=get_original_session_id(inv_context),
                    filename=artifact_filename,
                    content_bytes=artifact_bytes,
                    mime_type=final_mime_type,
                    metadata_dict={"description": f"Deep research report on: {research_question}"},
                    timestamp=timestamp_for_artifact,
                    schema_max_keys=50,  # Default schema max keys
                    tool_context=tool_context,
                )
            except Exception as save_error:
                log.error("%s Error saving artifact: %s", log_identifier, str(save_error))
                artifact_result = {"status": "error", "message": str(save_error)}
        
        if artifact_result.get("status") not in ["success", "partial_success"]:
            log.error("%s Failed to create artifact for research report. Status: %s, Message: %s",
                     log_identifier, artifact_result.get("status"), artifact_result.get("message"))
            artifact_version = None
        else:
            artifact_version = artifact_result.get("data_version", 1)
            log.info("%s Successfully created artifact '%s' v%d",
                    log_identifier, artifact_filename, artifact_version)
            
            # Send final progress update
            try:
                await _send_research_progress(
                    f"✅ Research complete! Report saved as '{artifact_filename}'",
                    tool_context,
                    phase="writing",
                    progress_percentage=100,
                    current_iteration=max_iterations,
                    total_iterations=max_iterations,
                    sources_found=len(all_findings),
                    elapsed_seconds=int(time.time() - start_time),
                    max_runtime_seconds=max_runtime_seconds or 0
                )
            except Exception as progress_error:
                log.error("%s Error sending final progress update: %s", log_identifier, str(progress_error))
            
            # Emit DeepResearchReportData signal directly to frontend
            # This bypasses the LLM response entirely, ensuring the report is displayed
            # via the DeepResearchReportBubble component 
            try:
                await _send_deep_research_report_signal(
                    artifact_filename=artifact_filename,
                    artifact_version=artifact_version,
                    title=citation_tracker.generated_title or research_question,
                    sources_count=len(all_findings),
                    tool_context=tool_context
                )

            except Exception as signal_error:
                log.error("%s Error sending deep research report signal: %s", log_identifier, str(signal_error))
        
        # Send final RAG info update marking research as complete
        try:
            await _send_rag_info_update(citation_tracker, tool_context, is_complete=True)
        except Exception as rag_error:
            log.error("%s Error sending final RAG info update: %s", log_identifier, str(rag_error))
        
        # Build the response - NO EMBED since we already sent the DeepResearchReportData signal
        artifact_save_success = artifact_result.get("status") in ["success", "partial_success"]
        artifact_version = artifact_result.get("data_version", 1) if artifact_save_success else None
        
        result_dict = {
            "status": "success",
            "total_sources": len(all_findings),
            "iterations_completed": min(iteration, max_iterations),
            "rag_metadata": citation_tracker.get_rag_metadata(artifact_filename=artifact_filename if artifact_save_success else None),
        }
        
        # Only include artifact info if save was successful
        if artifact_save_success:
            result_dict["artifact_filename"] = artifact_filename
            result_dict["artifact_version"] = artifact_version
            result_dict["response_artifact"] = {
                "filename": artifact_filename,
                "version": artifact_version
            }
            result_dict["message"] = (
                f"Deep research complete: analyzed {len(all_findings)} sources. "
                f"The comprehensive report '{artifact_filename}' (version {artifact_version}) "
                f"has been sent to the user and will be displayed automatically. "
                f"Do NOT include any artifact embeds or summarize the report - it is already being displayed."
            )
        else:
            result_dict["artifact_error"] = artifact_result.get("message", "Failed to save artifact")
            result_dict["message"] = f"Research complete but failed to save artifact: {artifact_result.get('message', 'Unknown error')}. Analyzed {len(all_findings)} sources."
        
        return result_dict
        
    except Exception as e:
        log.exception("%s Unexpected error: %s", log_identifier, e)
        return {
            "status": "error",
            "message": f"Research failed: {str(e)}"
        }


# Tool Definition
deep_research_tool_def = BuiltinTool(
    name="deep_research",
    implementation=deep_research,
    description="""
Performs comprehensive, iterative research across multiple sources.

This tool conducts deep research by:
1. Breaking down the research question into searchable queries
2. Searching across web and knowledge base sources
3. Reflecting on findings to identify gaps
4. Refining queries and conducting additional searches
5. Synthesizing findings into a comprehensive report with citations

Use this tool when you need to:
- Gather comprehensive information on a complex topic
- Research across multiple information sources
- Provide well-cited, authoritative answers
- Explore a topic in depth with multiple perspectives

The tool provides real-time progress updates and generates a detailed
research report with proper citations for all sources.

IMPORTANT - Returning Results:
The tool automatically sends the research report directly to the user's interface
via a special signal. The report will be displayed automatically in a dedicated
component. Do NOT include any artifact embeds or summarize the report content -
it is already being displayed to the user. Simply acknowledge that the research
is complete and the report has been delivered.

Configuration:
- Can be configured via tool_config in agent YAML (max_iterations, max_runtime_seconds, sources)
- Can be overridden via explicit parameters
- Supports research_type for backward compatibility ("quick" or "in-depth")
""",
    category="research",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:research:deep_research"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "research_question": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The research question or topic to investigate"
            ),
            "research_type": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Type of research: 'quick' (5min, 3 iterations) or 'in-depth' (10min, 10 iterations). Can be overridden by tool_config or explicit parameters. Default: 'quick'",
                enum=["quick", "in-depth"],
                nullable=True
            ),
            "max_iterations": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Maximum number of research iterations (1-10). Overrides tool_config and research_type if provided.",
                nullable=True
            ),
            "max_runtime_minutes": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Maximum runtime in minutes (1-10). The software converts this to seconds internally. Overrides tool_config and research_type if provided.",
                nullable=True
            ),
            "max_runtime_seconds": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Maximum runtime in seconds (60-600). Use max_runtime_minutes instead for easier specification. Overrides tool_config and research_type if provided.",
                nullable=True
            ),
            "sources": adk_types.Schema(
                type=adk_types.Type.ARRAY,
                items=adk_types.Schema(
                    type=adk_types.Type.STRING,
                    enum=["web", "kb"]
                ),
                description="Sources to search. Default from tool_config or ['web']. Web search requires Google Custom Search API key (GOOGLE_API_KEY and GOOGLE_CSE_ID). For other search providers (Tavily, Exa, Brave), use the corresponding plugins from solace-agent-mesh-plugins.",
                nullable=True
            ),
            "kb_ids": adk_types.Schema(
                type=adk_types.Type.ARRAY,
                items=adk_types.Schema(type=adk_types.Type.STRING),
                description="Specific knowledge base IDs to search (only used if 'kb' is in sources)",
                nullable=True
            )
        },
        required=["research_question"]
    ),
    examples=[]
)

# Register tool
tool_registry.register(deep_research_tool_def)

log.info("Deep research tool registered: deep_research")