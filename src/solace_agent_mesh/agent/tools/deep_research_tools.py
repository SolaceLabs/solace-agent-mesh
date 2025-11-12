"""
Deep Research Tools for Solace Agent Mesh

Provides comprehensive, iterative research capabilities across multiple sources
including web search, knowledge bases, Google Drive, and SharePoint.

This module implements:
- Iterative research with LLM-powered reflection and query refinement
- Multi-source search coordination
- Citation tracking and management
- Progress updates to frontend
- Comprehensive report generation
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from google.adk.tools import ToolContext
from google.genai import types as adk_types
from google.adk.models import LlmRequest
from solace_ai_connector.common.log import log

from .tool_definition import BuiltinTool
from .registry import tool_registry
from .web_search_tools import _web_search_tavily, _web_search_google
from .web_tools import web_request
from ...common import a2a


# Category information
CATEGORY_NAME = "Research & Analysis"
CATEGORY_DESCRIPTION = "Advanced research tools for comprehensive information gathering"


@dataclass
class SearchResult:
    """Represents a single search result from any source (web-only version)"""
    source_type: str  # "web", "kb" only
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


class ResearchCitationTracker:
    """Tracks citations throughout the research process"""
    
    def __init__(self, research_question: str):
        self.research_question = research_question
        self.citations: Dict[str, Dict[str, Any]] = {}
        self.citation_counter = 0
    
    def add_citation(self, result: SearchResult) -> str:
        """Add citation and return citation ID"""
        # Use 'search' prefix to match the citation rendering system
        citation_id = f"search{self.citation_counter}"
        log.info("[DeepResearch:Citation] Creating citation_id=%s (counter=%d) for: %s",
                 citation_id, self.citation_counter, result.title[:50])
        self.citation_counter += 1
        
        # Format like web_search tool for proper citation rendering
        self.citations[citation_id] = {
            "citation_id": citation_id,
            "file_id": f"deep_research_{self.citation_counter}",  # Add file_id for web citations
            "filename": result.title,  # Use title as filename
            "content_preview": result.content[:200] + "..." if len(result.content) > 200 else result.content,
            "relevance_score": result.relevance_score,
            "source_url": result.url or "N/A",  # Use source_url key (not just url)
            "metadata": {
                "title": result.title,
                "link": result.url,
                "type": "web_search",  # Mark as web_search type for proper rendering
                "source_type": result.source_type,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                **result.metadata
            }
        }
        
        result.citation_id = citation_id
        return citation_id
    
    def get_rag_metadata(self) -> Dict[str, Any]:
        """Format citations for RAG system"""
        return {
            "query": self.research_question,
            "search_type": "deep_research",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": list(self.citations.values())
        }


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
        
        logical_task_id = a2a_context.get("logical_task_id")
        context_id = a2a_context.get("contextId")
        
        # Create status update event using the standard data signal pattern
        status_update_event = a2a.create_data_signal_event(
            task_id=logical_task_id,
            context_id=context_id,
            signal_data=progress_data,
            agent_name=host_component.agent_name,
        )
        
        # Publish via the host component's async method
        loop = host_component.get_async_loop()
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                host_component._publish_status_update_with_buffer_flush(
                    status_update_event,
                    a2a_context,
                    skip_buffer_flush=False,
                ),
                loop,
            )
        else:
            log.error("%s Async loop not available. Cannot publish progress update.", log_identifier)
        
    except Exception as e:
        log.error("%s Error sending progress update: %s", log_identifier, str(e))


async def _search_web(
    query: str,
    max_results: int,
    tool_context: ToolContext,
    tool_config: Optional[Dict[str, Any]],
    send_progress: bool = True
) -> List[SearchResult]:
    """Search web using Google (default) or Tavily"""
    log_identifier = "[DeepResearch:WebSearch]"
    
    if send_progress:
        await _send_research_progress(
            f"Searching web for: {query[:60]}...",
            tool_context
        )
    
    # Check which providers are configured
    import os
    tavily_key = os.getenv("TAVILY_API_KEY")
    google_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    
    # Use Google by default (preferred for deep research)
    if google_key:
        log.info("%s Using Google search (default provider)", log_identifier)
        try:
            result = await _web_search_google(
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
            log.warning("%s Google search failed: %s, trying Tavily fallback", log_identifier, str(e))
            # Fall through to Tavily if Google fails
    
    # Try Tavily as fallback or if Google not configured
    if tavily_key:
        log.info("%s Using Tavily search %s", log_identifier, "(fallback)" if google_key else "(primary)")
        try:
            result = await _web_search_tavily(
                query=query,
                max_results=max_results,
                search_depth="advanced",
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
                        relevance_score=0.9,
                        metadata={"provider": "tavily"}
                    ))
                
                log.info("%s Found %d Tavily results", log_identifier, len(search_results))
                return search_results
                
        except Exception as e:
            log.warning("%s Tavily search failed: %s, trying Google fallback", log_identifier, str(e))
            
            # Fallback to Google
            if google_key:
                try:
                    result = await _web_search_google(
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
                        
                        log.info("%s Found %d Google results (fallback)", log_identifier, len(search_results))
                        return search_results
                        
                except Exception as e2:
                    log.error("%s Google fallback also failed: %s", log_identifier, str(e2))
    
    log.warning("%s No web search API configured (need TAVILY_API_KEY or GOOGLE_SEARCH_API_KEY)", log_identifier)
    return []


# KB search removed for web-only version

# Enterprise search functions removed for web-only version
# This version only supports web search and knowledge base search



async def _multi_source_search(
    query: str,
    sources: List[str],
    max_results_per_source: int,
    kb_ids: Optional[List[str]],
    tool_context: ToolContext,
    tool_config: Optional[Dict[str, Any]]
) -> List[SearchResult]:
    """Execute search across web and KB sources in parallel (web-only version)"""
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
    tool_context: ToolContext
) -> List[str]:
    """
    Generate 3-5 initial search queries using LLM.
    The LLM breaks down the research question into effective search queries.
    """
    log_identifier = "[DeepResearch:QueryGen]"
    
    try:
        inv_context = tool_context._invocation_context
        agent = getattr(inv_context, 'agent', None)
        
        if not agent:
            log.warning("%s No agent found, using fallback query generation", log_identifier)
            return [research_question]
        
        # Get the LLM from the agent
        llm = agent.canonical_model
        if not llm:
            log.warning("%s No LLM found, using fallback query generation", log_identifier)
            return [research_question]
        
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
        llm_request = LlmRequest(
            model=llm.model,
            contents=[adk_types.Content(role="user", parts=[adk_types.Part(text=query_prompt)])],
            config=adk_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7
            )
        )
        
        # Call LLM
        if hasattr(llm, 'generate_content_async'):
            async for response_event in llm.generate_content_async(llm_request):
                response = response_event
                break
        else:
            response = llm.generate_content(request=llm_request)
        
        # Extract text from response
        response_text = ""
        if hasattr(response, 'text') and response.text:
            response_text = response.text
        elif hasattr(response, 'parts') and response.parts:
            response_text = "".join([part.text for part in response.parts if hasattr(part, 'text') and part.text])
        
        query_data = json.loads(response_text)
        queries = query_data.get("queries", [research_question])[:5]
        
        log.info("%s Generated %d queries via LLM", log_identifier, len(queries))
        return queries
        
    except Exception as e:
        log.error("%s LLM query generation failed: %s, using fallback", log_identifier, str(e))
        return [research_question]


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
    max_iterations: int = 10
) -> ReflectionResult:
    """
    Reflect on current findings using LLM to determine next steps.
    
    The LLM analyzes the research findings to:
    1. Assess information completeness and quality
    2. Identify knowledge gaps
    3. Determine if more research is needed
    4. Generate refined search queries
    """
    log_identifier = "[DeepResearch:Reflection]"
    
    try:
        inv_context = tool_context._invocation_context
        agent = getattr(inv_context, 'agent', None)
        
        if not agent:
            log.error("%s No agent found for LLM reflection", log_identifier)
            return ReflectionResult(
                quality_score=0.5,
                gaps=["Unable to perform LLM reflection"],
                should_continue=False,
                suggested_queries=[],
                reasoning="No LLM available for reflection"
            )
        
        # Get the LLM from the agent
        llm = agent.canonical_model
        if not llm:
            log.error("%s No LLM found for reflection", log_identifier)
            return ReflectionResult(
                quality_score=0.5,
                gaps=["No LLM available"],
                should_continue=False,
                suggested_queries=[],
                reasoning="No LLM available for reflection"
            )
        
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
        llm_request = LlmRequest(
            model=llm.model,
            contents=[adk_types.Content(role="user", parts=[adk_types.Part(text=reflection_prompt)])],
            config=adk_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        
        # Call LLM
        if hasattr(llm, 'generate_content_async'):
            async for response_event in llm.generate_content_async(llm_request):
                response = response_event
                break
        else:
            response = llm.generate_content(request=llm_request)
        
        # Extract text from response
        response_text = ""
        if hasattr(response, 'text') and response.text:
            response_text = response.text
        elif hasattr(response, 'parts') and response.parts:
            response_text = "".join([part.text for part in response.parts if hasattr(part, 'text') and part.text])
        elif hasattr(response, 'content') and hasattr(response.content, 'parts'):
            response_text = "".join([part.text for part in response.content.parts if hasattr(part, 'text') and part.text])
        
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
        
        # Try to parse JSON response
        try:
            reflection_data = json.loads(response_text)
        except json.JSONDecodeError as je:
            log.warning("%s Failed to parse LLM JSON response: %s. Response text: %s",
                       log_identifier, str(je), response_text[:200])
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                try:
                    reflection_data = json.loads(json_match.group(1))
                except:
                    # Continue with fallback
                    should_continue = len(findings) < 15 and iteration < 3
                    return ReflectionResult(
                        quality_score=0.6,
                        gaps=["Need more sources"],
                        should_continue=should_continue,
                        suggested_queries=[f"{research_question} in depth", f"{research_question} latest"],
                        reasoning="Could not parse LLM response, using fallback"
                    )
            else:
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
    tool_context: ToolContext
) -> List[SearchResult]:
    """Use LLM to intelligently select which sources to fetch based on quality and relevance"""
    log_identifier = "[DeepResearch:SelectSources]"
    
    try:
        inv_context = tool_context._invocation_context
        agent = getattr(inv_context, 'agent', None)
        
        if not agent or not agent.canonical_model:
            log.warning("%s No LLM available, using fallback selection", log_identifier)
            # Fallback: just take top sources by relevance (web sources only for fetching)
            web_findings = [f for f in findings if f.source_type == "web" and f.url]
            return sorted(web_findings, key=lambda x: x.relevance_score, reverse=True)[:max_to_fetch]
        
        llm = agent.canonical_model
        
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

        log.info("%s Calling LLM for source selection", log_identifier)
        
        llm_request = LlmRequest(
            model=llm.model,
            contents=[adk_types.Content(role="user", parts=[adk_types.Part(text=selection_prompt)])],
            config=adk_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        
        if hasattr(llm, 'generate_content_async'):
            async for response_event in llm.generate_content_async(llm_request):
                response = response_event
                break
        else:
            response = llm.generate_content(request=llm_request)
        
        # Extract text from response with better error handling
        response_text = ""
        if hasattr(response, 'text') and response.text:
            response_text = response.text
        elif hasattr(response, 'parts') and response.parts:
            response_text = "".join([part.text for part in response.parts if hasattr(part, 'text') and part.text])
        elif hasattr(response, 'content') and hasattr(response.content, 'parts'):
            response_text = "".join([part.text for part in response.content.parts if hasattr(part, 'text') and part.text])
        
        if not response_text or not response_text.strip():
            log.warning("%s LLM returned empty response, using fallback selection", log_identifier)
            web_findings = [f for f in findings if f.source_type == "web" and f.url]
            return sorted(web_findings, key=lambda x: x.relevance_score, reverse=True)[:max_to_fetch]
        
        log.debug("%s LLM response text: %s", log_identifier, response_text[:200])
        
        # Try to parse JSON, with fallback for markdown-wrapped JSON
        try:
            selection_data = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                try:
                    selection_data = json.loads(json_match.group(1))
                    log.info("%s Extracted JSON from markdown code block", log_identifier)
                except json.JSONDecodeError as je2:
                    log.warning("%s Failed to parse extracted JSON: %s", log_identifier, str(je2))
                    raise
            else:
                # Try to find any JSON object in the response
                json_match = re.search(r'\{[^{}]*"selected_sources"[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        selection_data = json.loads(json_match.group(0))
                        log.info("%s Extracted JSON object from response", log_identifier)
                    except json.JSONDecodeError:
                        raise
                else:
                    raise
        
        selected_indices = selection_data.get("selected_sources", [])
        reasoning = selection_data.get("reasoning", "")
        
        if not selected_indices:
            log.warning("%s LLM returned empty selection, using fallback", log_identifier)
            web_findings = [f for f in findings if f.source_type == "web" and f.url]
            return sorted(web_findings, key=lambda x: x.relevance_score, reverse=True)[:max_to_fetch]
        
        log.info("%s LLM selected %d sources: %s", log_identifier, len(selected_indices), reasoning)
        
        # Convert 1-based indices to actual findings
        selected_sources = []
        for idx in selected_indices:
            if 1 <= idx <= len(web_findings):
                selected_sources.append(web_findings[idx - 1])
        
        return selected_sources[:max_to_fetch]
        
    except Exception as e:
        log.error("%s LLM source selection failed: %s, using fallback", log_identifier, str(e), exc_info=True)
        web_findings = [f for f in findings if f.source_type == "web" and f.url]
        return sorted(web_findings, key=lambda x: x.relevance_score, reverse=True)[:max_to_fetch]


async def _fetch_selected_sources(
    selected_sources: List[SearchResult],
    tool_context: ToolContext,
    tool_config: Optional[Dict[str, Any]],
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
        
        # Send progress for each source being fetched (simple message, no full structured data here)
        await _send_research_progress(
            f"Reading content from: {source.title[:50]}... ({i}/{len(selected_sources)})",
            tool_context
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
            tool_context
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
                # Extract citation number from citation_id (e.g., "search0" -> 0)
                citation_num = int(source.citation_id.replace("search", "").replace("file", "").replace("ref", ""))
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
                citation_num = int(source.citation_id.replace("search", "").replace("file", "").replace("ref", ""))
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
    tool_context: ToolContext
) -> str:
    """
    Generate comprehensive research report using LLM.
    The LLM synthesizes findings into a coherent narrative with proper citations.
    """
    log_identifier = "[DeepResearch:ReportGen]"
    log.info("%s Generating report from %d findings", log_identifier, len(all_findings))
    
    try:
        inv_context = tool_context._invocation_context
        agent = getattr(inv_context, 'agent', None)
        
        if not agent:
            log.error("%s No agent found for LLM report generation", log_identifier)
            return f"# Research Report: {research_question}\n\nError: Unable to generate report without LLM."
        
        # Get the LLM from the agent
        llm = agent.canonical_model
        if not llm:
            log.error("%s No LLM found for report generation", log_identifier)
            return f"# Research Report: {research_question}\n\nError: No LLM available."
        
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

REPORT STRUCTURE (3000-5000 words total):

## Executive Summary (300-500 words)
- Synthesize the MOST IMPORTANT insights from ALL sources
- Highlight key findings that answer the research question
- Provide context for why this topic matters
- DO NOT copy from any single source 

## Introduction (200-300 words)
- Explain the research question and its significance
- Provide historical or contextual background
- Outline what the report will cover
- Draw context from multiple sources [[cite:searchX]]

## Main Analysis (2000-3000 words)
Organize into 5-8 thematic sections. For EACH section:
- Create a descriptive heading (###)
- Write 300-500 words drawing information from multiple sources
- Start each paragraph with a topic sentence
- Support claims with citations from different sources [[cite:searchX]][[cite:searchY]]
- Explain implications and connections
- Compare and contrast different perspectives
- NEVER copy paragraphs from a single source

Example structure:
### [Theme 1 - e.g., "Historical Development"]
[Synthesize information from sources 0, 2, 5, 8...]

### [Theme 2 - e.g., "Economic Impact"]
[Synthesize information from sources 1, 3, 7, 9...]

## Comparative Analysis (400-600 words)
- Compare different perspectives across sources
- Identify agreements and contradictions
- Analyze why sources might differ
- Synthesize a balanced view
- Cite multiple sources for each point

## Implications (300-400 words)
- Discuss practical implications
- Identify applications or consequences
- Suggest areas needing further research
- Draw from multiple sources

## Conclusion (200-300 words)
- Synthesize the key takeaways from ALL sources
- Provide final analytical insights
- Suggest future directions

⚠️ DO NOT CREATE A REFERENCES SECTION: The system will automatically append a properly formatted References section with all cited sources. Your report should end with the Conclusion section.

CITATION RULES:
- Use [[cite:searchN]] format where N is the citation number from sources above
- Cite AFTER every factual claim
- Use multiple citations when multiple sources support a point: [[cite:search0]][[cite:search2]]
- Cite sources even when paraphrasing

QUALITY CHECKS:
✓ Have I synthesized from MULTIPLE sources (not just one)?
✓ Have I written in my OWN words (not copied)?
✓ Have I cited ALL factual claims?
✓ Have I reached 3000+ words?
✓ Have I organized information thematically (not source-by-source)?

Write your research report now. Format in Markdown.
"""

        log.info("%s Calling LLM for report generation", log_identifier)
        
        # Create LLM request with reasonable max tokens for faster generation
        # Reduced from 32000 to 8000 for better performance while still allowing comprehensive reports
        llm_request = LlmRequest(
            model=llm.model,
            contents=[adk_types.Content(role="user", parts=[adk_types.Part(text=report_prompt)])],
            config=adk_types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=8000  # Reduced from 32000 for faster generation
            )
        )
        
        # Call LLM with streaming and progress updates
        log.info("%s Starting LLM streaming for report generation", log_identifier)
        report_body = ""
        response_count = 0
        last_progress_update = 0
        
        async for response_event in llm.generate_content_async(llm_request):
            response_count += 1
            
            # Try different extraction methods
            extracted_text = ""
            if hasattr(response_event, 'text') and response_event.text:
                extracted_text = response_event.text
            elif hasattr(response_event, 'parts') and response_event.parts:
                extracted_text = "".join([part.text for part in response_event.parts if hasattr(part, 'text') and part.text])
            elif hasattr(response_event, 'content') and hasattr(response_event.content, 'parts'):
                extracted_text = "".join([part.text for part in response_event.content.parts if hasattr(part, 'text') and part.text])
            
            if extracted_text:
                report_body += extracted_text
                
                # Send progress update every 500 characters to show activity
                if len(report_body) - last_progress_update >= 500:
                    last_progress_update = len(report_body)
                    progress_pct = min(95, 85 + int((len(report_body) / 3000) * 10))  # 85-95%
                    log.info("%s Report generation progress: %d chars written", log_identifier, len(report_body))
        
        log.info("%s Report generation complete. Events: %d, Final length: %d chars", log_identifier, response_count, len(report_body))
        
        log.info("%s DEBUG: LLM returned report_body length: %d chars", log_identifier, len(report_body))
        log.info("%s DEBUG: Report body preview: %s", log_identifier, report_body[:500] if report_body else "[EMPTY]")
        
        # Add sources section
        report_body += "\n\n" + _generate_sources_section(all_findings)
        
        # Add methodology section
        report_body += "\n\n" + _generate_methodology_section(all_findings)
        
        log.info("%s LLM report generated: %d characters", log_identifier, len(report_body))
        
        return report_body
        
    except Exception as e:
        log.error("%s LLM report generation failed: %s", log_identifier, str(e))
        return f"# Research Report: {research_question}\n\nError generating report: {str(e)}"


async def deep_research(
    research_question: str,
    sources: Optional[List[str]] = None,
    max_iterations: int = 2,
    max_sources_per_iteration: int = 5,
    kb_ids: Optional[List[str]] = None,
    max_runtime_seconds: Optional[int] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Performs comprehensive, iterative research across multiple sources.
    
    Args:
        research_question: The research question or topic to investigate
        sources: Sources to search (default: ["web", "kb"])
        max_iterations: Maximum research iterations (default: 2, max: 10)
        max_sources_per_iteration: Max results per source per iteration (default: 5)
        kb_ids: Specific knowledge base IDs to search
        max_runtime_seconds: Maximum runtime in seconds (default: None = no limit)
        tool_context: ADK tool context
        tool_config: Tool configuration
    
    Returns:
        Dictionary with research report and metadata
    """
    log_identifier = "[DeepResearch]"
    log.info("%s Starting deep research: %s", log_identifier, research_question)
    
    if not tool_context:
        return {"status": "error", "message": "ToolContext is missing"}
    
    # Track start time for runtime limit
    import time
    start_time = time.time()
    
    # Default sources - web only
    if sources is None:
        sources = ["web"]
    else:
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
        
        # Generate initial queries using LLM
        queries = await _generate_initial_queries(research_question, tool_context)
        log.info("%s Generated %d initial queries", log_identifier, len(queries))
        
        # Iterative research loop
        all_findings: List[SearchResult] = []
        seen_sources_global = set()  # Track seen sources across ALL iterations
        
        for iteration in range(1, max_iterations + 1):
            # Check runtime limit
            if max_runtime_seconds:
                elapsed = time.time() - start_time
                if elapsed >= max_runtime_seconds:
                    log.info("%s Runtime limit reached (%d seconds), stopping research gracefully",
                            log_identifier, max_runtime_seconds)
                    await _send_research_progress(
                        f"Runtime limit reached. Generating report from {len(all_findings)} sources collected so far...",
                        tool_context
                    )
                    break
            
            log.info("%s === Iteration %d/%d ===", log_identifier, iteration, max_iterations)
            
            # Calculate progress percentage for this iteration
            iteration_progress_base = 10 + ((iteration - 1) / max_iterations) * 70  # 10-80% for iterations
            
            # Search with current queries
            iteration_findings = []
            for query_idx, query in enumerate(queries, 1):
                # Calculate sub-progress within iteration
                query_progress = iteration_progress_base + (query_idx / len(queries)) * (70 / max_iterations) * 0.3
                
                # Send progress for each query with structured data
                await _send_research_progress(
                    f"Query {query_idx}/{len(queries)}: {query[:60]}...",
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
                for result in results:
                    # For web sources, use URL or title as unique key
                    key = result.url or f"web:{result.title}"
                    
                    # Only add if not seen before
                    if key not in seen_sources_global:
                        seen_sources_global.add(key)
                        iteration_findings.append(result)
            
            # Add citations for new findings
            for finding in iteration_findings:
                citation_tracker.add_citation(finding)
            
            all_findings.extend(iteration_findings)
            
            log.info("%s Iteration %d found %d new sources (total: %d)",
                    log_identifier, iteration, len(iteration_findings), len(all_findings))
            
            # Select and fetch full content from best sources in THIS iteration
            # This allows the LLM to reflect on full content, not just snippets
            selection_progress = iteration_progress_base + (70 / max_iterations) * 0.4
            
            # Prepare URL list early for the entire analyzing phase
            fetching_url_list = []
            
            # Select top 2-3 sources from this iteration to fetch/analyze
            sources_to_display_count = min(3, len(all_findings))
            
            # For web sources: select and fetch full content from current iteration
            selected_sources = []
            if len(iteration_findings) > 0:
                sources_to_fetch_count = min(3, len(iteration_findings))
                selected_sources = await _select_sources_to_fetch(
                    research_question, iteration_findings, max_to_fetch=sources_to_fetch_count, tool_context=tool_context
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
                fetch_stats = await _fetch_selected_sources(selected_sources, tool_context, tool_config, start_time, max_runtime_seconds)
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
                research_question, all_findings, iteration, tool_context, max_iterations
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
            research_question, all_findings, citation_tracker, tool_context
        )
        
        log.info("%s Research complete: %d total sources, report length: %d chars",
                log_identifier, len(all_findings), len(report))
        
        # Create artifact for the research report
        from ..tools.builtin_artifact_tools import _internal_create_artifact
        from ..adk.tool_wrapper import ADKToolWrapper
        
        # Generate filename from research question
        import re
        safe_filename = re.sub(r'[^\w\s-]', '', research_question.lower())
        safe_filename = re.sub(r'[-\s]+', '_', safe_filename)
        safe_filename = safe_filename[:50]  # Limit length
        artifact_filename = f"{safe_filename}_report.md"
        
        # Create the artifact - IMPORTANT: Use original tool_context to preserve state
        a2a_ctx_check = tool_context.state.get("a2a_context")
        log.info("%s DEBUG: a2a_context present in tool_context.state: %s",
                log_identifier, a2a_ctx_check is not None)
        if a2a_ctx_check:
            log.info("%s DEBUG: a2a_context.logical_task_id: %s",
                    log_identifier, a2a_ctx_check.get("logical_task_id"))
        
        wrapped_creator = ADKToolWrapper(
            original_func=_internal_create_artifact,
            tool_config=None,
            tool_name="_internal_create_artifact",
            origin="internal",
            resolution_type="early",
        )
        
        # Use the ORIGINAL tool_context, not a new one, to preserve a2a_context
        artifact_result = await wrapped_creator(
            filename=artifact_filename,
            content=report,
            mime_type="text/markdown",
            description=f"Deep research report on: {research_question}",
            tool_context=tool_context,  # Changed from tool_context_for_artifact
        )
        
        if artifact_result.get("status") not in ["success", "partial_success"]:
            log.warning("%s Failed to create artifact for research report", log_identifier)
            artifact_version = None
        else:
            artifact_version = artifact_result.get("data_version", 1)
            log.info("%s Successfully created artifact '%s' v%d",
                    log_identifier, artifact_filename, artifact_version)
            
            # Send final progress update
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
        
        result_dict = {
            "status": "success",
            "message": f"Research complete: analyzed {len(all_findings)} sources. Report saved as artifact '{artifact_filename}'.\n\nHere is the research report:\n\n{report}\n\n[[artifact:{artifact_filename}]]",
            "report": report,
            "artifact_filename": artifact_filename,
            "artifact_version": artifact_result.get("data_version", 1) if artifact_result.get("status") in ["success", "partial_success"] else None,
            "total_sources": len(all_findings),
            "iterations_completed": min(iteration, max_iterations),
            "rag_metadata": citation_tracker.get_rag_metadata()
        }
        
        return result_dict
        
    except Exception as e:
        log.exception("%s Unexpected error: %s", log_identifier, e)
        return {
            "status": "error",
            "message": f"Research failed: {str(e)}"
        }


# Import the wrapper
from .deep_research_wrapper import deep_research_with_auto_params

# Tool Definition
deep_research_tool_def = BuiltinTool(
    name="deep_research",
    implementation=deep_research_with_auto_params,
    description="""
Performs comprehensive, iterative research across multiple sources.

This tool conducts deep research by:
1. Breaking down the research question into searchable queries
2. Searching across web, knowledge bases, and enterprise sources
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
            "sources": adk_types.Schema(
                type=adk_types.Type.ARRAY,
                items=adk_types.Schema(
                    type=adk_types.Type.STRING,
                    enum=["web", "kb"]
                ),
                description="Sources to search (default: ['web', 'kb']). Web search requires Google or Tavily API keys. KB search requires configured knowledge bases.",
                nullable=True
            ),
            "max_iterations": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Maximum research iterations (default: 2, max: 3)",
                minimum=1,
                maximum=5,
                nullable=True
            ),
            "max_sources_per_iteration": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Maximum results per source per iteration (default: 5)",
                minimum=1,
                maximum=10,
                nullable=True
            ),
            "kb_ids": adk_types.Schema(
                type=adk_types.Type.ARRAY,
                items=adk_types.Schema(type=adk_types.Type.STRING),
                description="Specific knowledge base IDs to search",
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