# =============================================================================
# ADK PATCHES - Two separate patches to modify ADK behavior
# =============================================================================

# =============================================================================
# PATCH 1: Event Content Processing
# Purpose: Fix event filtering and function response handling in LLM flows
# =============================================================================
import google.adk.flows.llm_flows.contents
from google.adk.flows.llm_flows.contents import _contains_empty_content
from google.adk.flows.llm_flows.contents import _is_event_belongs_to_branch
from google.adk.flows.llm_flows.contents import _is_auth_event
from google.adk.flows.llm_flows.contents import _present_other_agent_message
from google.adk.flows.llm_flows.contents import _is_other_agent_reply
from google.adk.flows.llm_flows.contents import _rearrange_events_for_async_function_responses_in_history
from google.adk.flows.llm_flows.contents import remove_client_function_call_id
from google.adk.events.event import Event

import copy
from typing import Optional

from google.genai import types

def _patch_get_contents(
    current_branch: Optional[str], events: list[Event], agent_name: str = ''
) -> list[types.Content]:
  """Get the contents for the LLM request.

  Applies filtering, rearrangement, and content processing to events.

  Args:
    current_branch: The current branch of the agent.
    events: Events to process.
    agent_name: The name of the agent.

  Returns:
    A list of processed contents.
  """
  filtered_events = []
  # Parse the events, leaving the contents and the function calls and
  # responses from the current agent.
  for event in events:
    if _contains_empty_content(event):
      continue
    if not _is_event_belongs_to_branch(current_branch, event):
      # Skip events not belong to current branch.
      continue
    if _is_auth_event(event):
      # Skip auth events.
      continue
    if _is_other_agent_reply(agent_name, event):
      if converted_event := _present_other_agent_message(event):
        filtered_events.append(converted_event)
    else:
      filtered_events.append(event)

  # Rearrange events for proper function call/response pairing
  result_events = filtered_events
  result_events = _rearrange_events_for_async_function_responses_in_history(
      result_events
  )

  # Convert events to contents
  contents = []
  for event in result_events:
    content = copy.deepcopy(event.content)
    remove_client_function_call_id(content)
    contents.append(content)
  return contents

# =============================================================================
# PATCH 2: Long-Running Tool Support
# Purpose: Modify BaseLlmFlow.run_async to properly handle long-running tools
# =============================================================================
from google.adk.flows.llm_flows.base_llm_flow import BaseLlmFlow
from google.adk.agents.invocation_context import InvocationContext
from typing import AsyncGenerator

async def patch_run_async(
    self, invocation_context: InvocationContext
) -> AsyncGenerator[Event, None]:
    """Runs the flow."""
    while True:
        last_event = None
        has_long_running_call = False
        async for event in self._run_one_step_async(invocation_context):
            last_event = event
            if event.long_running_tool_ids:
                has_long_running_call = True
            yield event
        if not last_event or last_event.is_final_response() or has_long_running_call:
            break
        if last_event.partial:
            # TODO: handle this in BaseLlm level.
            raise ValueError(
                f"Last event shouldn't be partial. LLM max output limit may be"
                f' reached.'
                )

def patch_adk():
    """Patch the ADK to use the custom get_contents and run_async methods."""
    google.adk.flows.llm_flows.contents._get_contents = _patch_get_contents
    BaseLlmFlow.run_async = patch_run_async
