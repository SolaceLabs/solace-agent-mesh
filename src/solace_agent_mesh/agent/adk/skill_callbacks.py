"""
Skill Learning Callbacks for ADK Agents.

This module provides callbacks for integrating the skill learning system
with the ADK agent execution pipeline. It includes:
- Skill injection into system prompts
- Task completion hooks for skill learning
- Broker-based learning nomination for standalone skill learning service
"""

import json
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent

log = logging.getLogger(__name__)

# Topic pattern for nominating tasks for learning
# The skill learning service subscribes to: sam/+/task/nominate-for-learning
LEARNING_NOMINATION_TOPIC_TEMPLATE = "sam/{agent_name}/task/nominate-for-learning"


def _get_skill_injector(host_component: "SamAgentComponent"):
    """
    Get or create the skill injector for a component.
    
    Returns None if skill learning is not enabled.
    """
    log_identifier = "[SkillInjector:Init]"
    
    # Check if skill learning is enabled
    skill_config = host_component.get_config("skill_learning", {})
    if not skill_config.get("enabled", False):
        log.debug("%s Skill learning not enabled", log_identifier)
        return None
    
    # Check if injector is already cached
    if hasattr(host_component, "_skill_injector"):
        log.debug("%s Returning cached skill injector", log_identifier)
        return host_component._skill_injector
    
    try:
        from ...services.skill_learning import (
            AgentSkillInjector,
            VersionedSkillService,
            VersionedSkillRepository,
            EmbeddingService,
            StaticSkillLoader,
        )
        
        log.info("%s Creating new skill injector...", log_identifier)
        
        # Get database session factory
        db_session_factory = host_component.get_agent_specific_state("db_session_factory")
        if not db_session_factory:
            log.warning(
                "%s Skill learning enabled but no database session factory available. "
                "Make sure agent_init_function is configured with skill_learning_init.",
                log_identifier,
            )
            return None
        
        log.info("%s Got database session factory", log_identifier)
        
        # Create versioned repository (uses skill_groups and skill_versions tables)
        repository = VersionedSkillRepository(db_session_factory)
        
        # Create embedding service if configured
        embedding_service = None
        embedding_config = skill_config.get("embedding", {})
        if embedding_config.get("enabled", True):
            use_litellm = embedding_config.get("use_litellm", True)
            model = embedding_config.get("model", "text-embedding-3-small")
            api_key = embedding_config.get("api_key")
            
            if use_litellm:
                # Use LiteLLM provider
                embedding_service = EmbeddingService(
                    provider_type="litellm",
                    model=model,
                    api_key=api_key,
                    api_base=embedding_config.get("api_base"),
                )
            else:
                # Use OpenAI provider directly
                embedding_service = EmbeddingService(
                    provider_type="openai",
                    model=model,
                    api_key=api_key,
                    base_url=embedding_config.get("base_url"),
                )
        
        # Create static skill loader if configured
        static_loader = None
        static_config = skill_config.get("static_skills", {})
        log.info("%s Static skills config: %s", log_identifier, static_config)
        if static_config.get("enabled", True):
            skills_directory = static_config.get("directory", "skills")
            log.info("%s Loading static skills from: %s", log_identifier, skills_directory)
            try:
                static_loader = StaticSkillLoader(skills_directory)
                # Try to load skills immediately to verify
                all_skills = static_loader.load_all_skills()
                log.info(
                    "%s Static skill loader initialized for %s, found %d skills",
                    log_identifier,
                    skills_directory,
                    len(all_skills),
                )
            except Exception as e:
                log.warning(
                    "%s Failed to initialize static skill loader: %s",
                    log_identifier,
                    e,
                )
        
        # Create versioned skill service (compatible with gateway's skill storage)
        skill_service = VersionedSkillService(
            repository=repository,
            embedding_service=embedding_service,
            static_loader=static_loader,
        )
        
        # Create injector
        injector = AgentSkillInjector(
            skill_service=skill_service,
            max_skills_in_prompt=skill_config.get("max_skills_in_prompt", 10),
            enable_skill_tools=skill_config.get("enable_skill_tools", True),
        )
        
        # Cache it
        host_component._skill_injector = injector
        log.info(
            "%s Initialized skill learning injector with versioned skill service.",
            host_component.log_identifier,
        )
        
        return injector
        
    except ImportError as e:
        log.warning(
            "%s Skill learning dependencies not available: %s",
            host_component.log_identifier,
            e,
        )
        return None
    except Exception as e:
        log.error(
            "%s Failed to initialize skill learning: %s",
            host_component.log_identifier,
            e,
        )
        return None


def inject_skills_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
    host_component: "SamAgentComponent",
) -> Optional[LlmResponse]:
    """
    ADK before_model_callback to inject skill summaries and nomination instructions into the system prompt.
    
    This implements Level 1 of progressive disclosure - brief skill summaries
    that help the agent know what skills are available, plus instructions for
    when to nominate tasks for learning.
    
    Args:
        callback_context: The ADK callback context
        llm_request: The LLM request being prepared
        host_component: The host component instance
        
    Returns:
        None (modifies llm_request in place)
    """
    log_identifier = "[Callback:InjectSkills]"
    log.info("%s Running skill injection callback...", log_identifier)
    
    if not host_component:
        log.error(
            "%s Host component instance not provided. Cannot inject skills.",
            log_identifier,
        )
        return None
    
    # Check if skill learning is enabled
    skill_config = host_component.get_config("skill_learning", {})
    if not skill_config.get("enabled", False):
        log.info(
            "%s Skill learning not enabled.",
            log_identifier,
        )
        return None
    
    log.info(
        "%s Skill learning is enabled, proceeding with skill injection...",
        log_identifier,
    )
    
    try:
        # Get context from callback
        a2a_context = callback_context.state.get("a2a_context", {})
        user_id = a2a_context.get("user_id")
        agent_name = host_component.get_config("agent_name")
        
        # Get task context from the first user message
        task_context = None
        if llm_request.contents:
            for content in llm_request.contents:
                if content.role == "user" and content.parts:
                    for part in content.parts:
                        if part.text:
                            task_context = part.text
                            break
                    if task_context:
                        break
        
        # Build the skill learning section
        skill_sections = []
        
        # Try to get skill summaries from injector (if available)
        injector = _get_skill_injector(host_component)
        log.info(
            "%s Got skill injector: %s",
            log_identifier,
            "yes" if injector else "no",
        )
        if injector:
            log.info(
                "%s Calling get_skills_for_prompt with agent=%s, user=%s, task_context=%s",
                log_identifier,
                agent_name,
                user_id,
                task_context[:100] if task_context else None,
            )
            skill_section = injector.get_skills_for_prompt(
                agent_name=agent_name,
                user_id=user_id,
                task_context=task_context,
            )
            log.info(
                "%s Got skill section: %s",
                log_identifier,
                skill_section[:200] if skill_section else "empty",
            )
            if skill_section:
                skill_sections.append(skill_section)
        
        # Always add nomination instructions when skill learning is enabled
        from ..tools.nominate_for_learning_tool import get_nominate_for_learning_instruction
        nomination_instructions = get_nominate_for_learning_instruction()
        skill_sections.append(nomination_instructions)
        
        if not skill_sections:
            log.debug(
                "%s No skill learning content to inject for agent %s.",
                log_identifier,
                agent_name,
            )
            return None
        
        # Combine all skill learning sections
        combined_section = "\n\n".join(skill_sections)
        
        # Inject into system instruction
        if llm_request.config is None:
            log.warning(
                "%s llm_request.config is None, cannot inject skill learning instructions.",
                log_identifier,
            )
            return None
        
        if llm_request.config.system_instruction is None:
            llm_request.config.system_instruction = ""
        
        if llm_request.config.system_instruction:
            llm_request.config.system_instruction += "\n\n---\n\n" + combined_section
        else:
            llm_request.config.system_instruction = combined_section
        
        log.info(
            "%s Injected skill learning instructions into system prompt for agent %s.",
            log_identifier,
            agent_name,
        )
        
    except Exception as e:
        log.error(
            "%s Error injecting skill learning instructions: %s",
            log_identifier,
            e,
        )
    
    return None


async def on_task_complete_skill_learning(
    host_component: "SamAgentComponent",
    a2a_context: Dict[str, Any],
    success: bool,
) -> None:
    """
    Handle task completion for skill learning.
    
    This is called when a task completes. By default, it does nothing because
    skill learning nominations should come from the LLM calling the
    `nominate_for_learning` tool explicitly.
    
    The agent decides which tasks are worth learning from based on:
    - Novel approaches or creative solutions
    - Complex multi-step procedures
    - Successful handling of edge cases
    - Tasks that could benefit from reusable patterns
    
    Configuration options:
    - nomination_mode: "broker" (default) - publish to broker for standalone service
                      "local" - process locally with in-process skill learning
                      "both" - both broker and local processing
    
    Args:
        host_component: The host component instance
        a2a_context: The A2A context for the task
        success: Whether the task succeeded
    """
    log_identifier = "[SkillLearning:TaskComplete]"
    
    # All nominations must come from the LLM calling the nominate_for_learning tool.
    # This ensures the agent makes intelligent decisions about what's worth learning.
    
    if not success:
        log.debug(
            "%s Task was not successful, no skill learning action needed.",
            log_identifier,
        )
        return
    
    # Check if skill learning is enabled
    skill_config = host_component.get_config("skill_learning", {})
    if not skill_config.get("enabled", False):
        return
    
    # Log deprecation warning if old nomination_strategy is still configured
    nomination_strategy = skill_config.get("nomination_strategy")
    if nomination_strategy and nomination_strategy != "tool":
        log.warning(
            "%s The 'nomination_strategy' config option is deprecated. "
            "All nominations now come from the LLM calling the nominate_for_learning tool. "
            "Please remove 'nomination_strategy' from your config.",
            log_identifier,
        )
    
    log.debug(
        "%s Task completed successfully. Skill learning nomination (if any) "
        "will come from the LLM calling the nominate_for_learning tool.",
        log_identifier,
    )


async def _publish_learning_nomination(
    host_component: "SamAgentComponent",
    task_id: str,
    agent_name: str,
    user_id: Optional[str],
    session_id: Optional[str],
    a2a_context: Dict[str, Any],
    log_identifier: str,
) -> None:
    """
    Publish a learning nomination message to the broker.
    
    The standalone skill learning service subscribes to these messages
    and processes them asynchronously.
    
    Args:
        host_component: The host component instance
        task_id: The task ID to nominate
        agent_name: The agent that completed the task
        user_id: The user who initiated the task
        session_id: The session ID
        a2a_context: The A2A context for additional metadata
        log_identifier: Log prefix for consistent logging
    """
    try:
        # Build the nomination topic
        topic = LEARNING_NOMINATION_TOPIC_TEMPLATE.format(agent_name=agent_name)
        
        # Build the nomination payload
        nomination_payload = {
            "task_id": task_id,
            "agent_name": agent_name,
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": time.time(),
            "metadata": {
                "context_id": a2a_context.get("contextId"),
                "client_id": a2a_context.get("client_id"),
                "gateway_id": a2a_context.get("gateway_id"),
            },
        }
        
        # Publish to broker
        host_component.publish_a2a_message(
            payload=nomination_payload,
            topic=topic,
        )
        
        log.info(
            "%s Published learning nomination to %s for task %s",
            log_identifier,
            topic,
            task_id,
        )
        
    except Exception as e:
        log.error(
            "%s Failed to publish learning nomination for task %s: %s",
            log_identifier,
            task_id,
            e,
        )


def generate_skill_tool_instruction() -> str:
    """
    Generate instruction text for the skill_read tool.
    
    Returns:
        Instruction text for the system prompt
    """
    return """\
**Skill Reading Tool (`skill_read`):**

You have access to a `skill_read` tool that retrieves detailed procedures for learned skills.

When to use `skill_read`:
- When you see a skill in the "Available Skills" section that matches the user's request
- When you need step-by-step guidance for a complex task
- When you want to follow a proven procedure

Parameters:
- `skill_name` (required): The name of the skill to read

The tool returns:
- Full procedure steps
- Required tools and their usage
- Example inputs/outputs
- Success criteria

Example:
```
skill_read(skill_name="Create Sales Report")
```

Use the returned procedure to guide your task execution.
"""