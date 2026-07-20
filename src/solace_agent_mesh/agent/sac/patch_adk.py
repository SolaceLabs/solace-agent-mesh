# =============================================================================
# ADK PATCHES - Two separate patches to modify ADK behavior
# =============================================================================

# =============================================================================
# PATCH 1: Event Content Processing
# Purpose: Filter whitespace-only text parts out of LLM request contents.
# Some LLM providers reject requests containing text content blocks with only
# whitespace characters; ADK's _contains_empty_content only drops truly empty
# content, not whitespace-only content like ' '.
#
# Implemented as a wrapper around ADK's _get_contents (rather than a vendored
# copy of its body, as pre-2.x versions of this patch did) so we don't have to
# track ADK's internal rewind/compaction/isolation logic across upgrades.
# =============================================================================
import logging
import os
from collections.abc import AsyncGenerator

import google.adk.flows.llm_flows.contents
from google.adk.events.event import Event
from google.adk.utils.context_utils import Aclosing
from google.genai import types

logger = logging.getLogger(__name__)


def _filter_whitespace_only_text_parts_inplace(content: types.Content) -> bool:
    """Filter out whitespace-only text parts from content IN-PLACE.

    - First, do a quick scan to check if ANY whitespace-only text parts exist
    - Only if found, then create the filtered list and do the actual filtering

    Only replaces the top-level ``parts`` list (never mutates nested Part
    fields), which is the mutation contract ADK's request-isolated content
    copies allow.

    Args:
        content: The content to filter (modified in-place if needed).

    Returns:
        True if content still has valid parts after filtering.
        False if all parts were removed (content should be skipped).
    """
    if not content or not content.parts:
        return bool(content and content.parts)

    has_whitespace_only = False
    for part in content.parts:
        if hasattr(part, "text") and part.text is not None:
            if not part.text.strip():
                has_whitespace_only = True
                break

    if not has_whitespace_only:
        return True

    filtered_parts = []
    for part in content.parts:
        # Keep function calls and function responses
        if hasattr(part, "function_call") and part.function_call:
            filtered_parts.append(part)
        elif hasattr(part, "function_response") and part.function_response:
            filtered_parts.append(part)
        # For text parts, only keep if they have non-whitespace content
        elif hasattr(part, "text") and part.text is not None:
            if part.text.strip():
                filtered_parts.append(part)
            # Skip whitespace-only text parts
        else:
            # Keep any other part types
            filtered_parts.append(part)

    # If no parts remain, signal this content should be skipped
    if not filtered_parts:
        return False

    content.parts = filtered_parts
    return True


_original_get_contents = google.adk.flows.llm_flows.contents._get_contents


def _patch_get_contents(*args, **kwargs) -> list[types.Content]:
    """Post-filter ADK's request contents, dropping whitespace-only text parts.

    Delegates entirely to ADK's own _get_contents (rewinds, compaction,
    isolation scopes, transcription merging, id stripping) and then removes
    whitespace-only text parts, skipping contents left with no parts at all.
    """
    contents = _original_get_contents(*args, **kwargs)
    return [
        content
        for content in contents
        if _filter_whitespace_only_text_parts_inplace(content)
    ]


# =============================================================================
# PATCH 2: Long-Running Tool Support
# Purpose: Modify BaseLlmFlow.run_async to properly handle long-running tools
# =============================================================================
from google.adk.agents.invocation_context import InvocationContext
from google.adk.flows.llm_flows.base_llm_flow import BaseLlmFlow


async def patch_run_async(
    self, invocation_context: InvocationContext
) -> AsyncGenerator[Event, None]:
    """Runs the flow.

    Mirrors ADK's BaseLlmFlow.run_async, adding one behavior: stop looping
    into another LLM step once an event carries long_running_tool_ids, so the
    invocation pauses at the long-running tool call instead of re-prompting
    the model while the tool is still in flight.
    """
    while True:
        last_event = None
        has_long_running_call = False
        async with Aclosing(self._run_one_step_async(invocation_context)) as agen:
            async for event in agen:
                last_event = event
                if event.long_running_tool_ids:
                    has_long_running_call = True
                yield event
        if (
            not last_event
            or last_event.is_final_response()
            or last_event.partial
            or has_long_running_call
        ):
            if last_event and last_event.partial:
                logger.warning("The last event is partial, which is not expected.")
            break


def patch_adk():
    """Patch the ADK to use the custom get_contents and run_async methods."""
    # ADK 2.x defaults GOOGLE_API_USE_CLIENT_CERTIFICATE to 'true', making the
    # MCP session manager probe Google ADC (incl. multi-second GCE metadata
    # timeouts off-GCP) for every HTTP MCP connection. SAM's MCP servers are
    # not Google APIs, so default it off; an explicit env var still wins.
    os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

    google.adk.flows.llm_flows.contents._get_contents = _patch_get_contents
    BaseLlmFlow.run_async = patch_run_async
