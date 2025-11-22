"""
Deep Research Tool Wrapper with Simplified User Interaction

This wrapper prompts users to choose between "quick search" or "in-depth" research,
then translates that choice into appropriate runtime parameters.
"""

from typing import Any, Dict, List, Optional
from google.adk.tools import ToolContext
from solace_ai_connector.common.log import log

from .deep_research_tools import deep_research


async def deep_research_with_auto_params(
    research_question: str,
    research_type: str = "quick",
    sources: Optional[List[str]] = None,
    max_iterations: int = 2,
    max_sources_per_iteration: int = 5,
    kb_ids: Optional[List[str]] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Wrapper for deep_research that translates research type to runtime parameters.
    
    This function:
    1. Takes a simple research_type parameter ("quick" or "in-depth")
    2. Translates it to appropriate runtime limits:
       - "quick": 5 minutes (300 seconds), 2 iterations
       - "in-depth": 10 minutes (600 seconds), 3 iterations
    3. Calls the actual deep_research function with these parameters
    
    This provides a simplified interface that doesn't confuse users with technical settings.
    """
    log_identifier = "[DeepResearchWrapper]"
    
    log.info("%s Wrapper called with research_type=%s", log_identifier, research_type)
    
    # Translate research type to runtime parameters
    if research_type.lower() in ["in-depth", "indepth", "in_depth", "deep", "comprehensive"]:
        max_runtime_seconds = 600  # 10 minutes
        max_iterations = 10
        research_mode = "in-depth"
        log.info("%s Using IN-DEPTH mode: 10 minutes, 10 iterations", log_identifier)
    else:
        # Default to quick search for any other value
        max_runtime_seconds = 300  # 5 minutes
        max_iterations = 3
        research_mode = "quick"
        log.info("%s Using QUICK mode: 5 minutes, 3 iterations", log_identifier)
    
    # Set default sources if not provided
    if sources is None:
        sources = ["web"]
        log.info("%s Using default sources: %s", log_identifier, sources)
    
    log.info("%s Final parameters: mode=%s, duration=%ds, iterations=%d, sources=%s",
            log_identifier, research_mode, max_runtime_seconds, max_iterations, sources)
    
    # Call the actual deep_research function with translated parameters
    return await deep_research(
        research_question=research_question,
        sources=sources,
        max_iterations=max_iterations,
        max_sources_per_iteration=max_sources_per_iteration,
        kb_ids=kb_ids,
        max_runtime_seconds=max_runtime_seconds,
        tool_context=tool_context,
        tool_config=tool_config,
    )