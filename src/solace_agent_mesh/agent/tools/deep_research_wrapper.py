"""
Deep Research Tool Wrapper with Automatic Parameter Injection

This wrapper automatically extracts deep_research_settings from the message metadata
and injects them into the tool call, ensuring user preferences are always respected
regardless of what parameters the LLM provides.
"""

from typing import Any, Dict, List, Optional
from google.adk.tools import ToolContext
from solace_ai_connector.common.log import log

from .deep_research_tools import deep_research


async def deep_research_with_auto_params(
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
    Wrapper for deep_research that automatically injects parameters from metadata.
    
    This function:
    1. Extracts deep_research_settings from the task context metadata
    2. Overrides LLM-provided parameters with user's preferences
    3. Calls the actual deep_research function with corrected parameters
    
    This ensures user settings are ALWAYS respected, regardless of what the LLM provides.
    """
    log_identifier = "[DeepResearchWrapper]"
    
    log.info("%s Wrapper called with LLM parameters: max_runtime_seconds=%s, max_iterations=%s, sources=%s",
            log_identifier, max_runtime_seconds, max_iterations, sources)
    
    # Extract metadata from tool context
    if tool_context and tool_context.state:
        a2a_context = tool_context.state.get("a2a_context", {})
        log.info("%s Found a2a_context in tool_context.state", log_identifier)
        
        # Try to get the original message metadata
        # The metadata should be available in the a2a_context
        original_metadata = a2a_context.get("original_message_metadata", {})
        log.info("%s original_message_metadata keys: %s", log_identifier, list(original_metadata.keys()))
        
        # Check for deep_research_settings in metadata
        if "deep_research_settings" in original_metadata:
            settings = original_metadata["deep_research_settings"]
            log.info("%s Found deep_research_settings in metadata: %s", log_identifier, settings)
            
            # Override parameters with user's settings
            if "max_runtime_seconds" in settings and settings["max_runtime_seconds"]:
                max_runtime_seconds = settings["max_runtime_seconds"]
                log.info("%s Overriding max_runtime_seconds with user setting: %d", 
                        log_identifier, max_runtime_seconds)
            
            if "max_iterations" in settings and settings["max_iterations"]:
                max_iterations = settings["max_iterations"]
                log.info("%s Overriding max_iterations with user setting: %d", 
                        log_identifier, max_iterations)
            
            if "sources" in settings and settings["sources"]:
                sources = settings["sources"]
                log.info("%s Overriding sources with user setting: %s", 
                        log_identifier, sources)
            
            log.info("%s ✅ Applied user settings from metadata: duration=%ds, iterations=%d, sources=%s",
                    log_identifier, max_runtime_seconds or 0, max_iterations, sources or "default")
        else:
            log.warning("%s ⚠️ No deep_research_settings found in metadata, using LLM-provided or default parameters",
                       log_identifier)
    else:
        log.warning("%s ⚠️ No tool_context or tool_context.state available", log_identifier)
    
    log.info("%s Calling deep_research with final parameters: max_runtime_seconds=%s, max_iterations=%s, sources=%s",
            log_identifier, max_runtime_seconds, max_iterations, sources)
    
    # Call the actual deep_research function with (potentially overridden) parameters
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