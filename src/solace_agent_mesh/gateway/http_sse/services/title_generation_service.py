"""
Service for generating chat session titles using LLM.
"""
import asyncio
import logging
from typing import Optional
from google.adk.models import BaseLlm
from ....agent.adk.models.lite_llm import LiteLlm

from .title_generation_constants import (
    MAX_USER_MESSAGE_LENGTH,
    MAX_AGENT_RESPONSE_LENGTH,
    MAX_TITLE_LENGTH,
    TITLE_CHAR_LIMIT,
    DEFAULT_TEMPERATURE,
)

log = logging.getLogger(__name__)


class TitleGenerationService:
    """
    Generates concise, meaningful titles for chat sessions using LiteLLM.
    """

    def __init__(self, model_config: dict, llm: BaseLlm):
 
        # Use title-specific model if available, fallback to general model
        title_model = model_config.get("llm_service_title_model_name")
        if title_model:
            self.llm = LiteLlm(model=title_model, **model_config)
        else:
            self.llm = llm
        log.info(f"TitleGenerationService initialized with LiteLLM instance")

    async def generate_title_async(
        self,
        session_id: str,
        user_message: str,
        agent_response: str,
        user_id: str,
        update_callback: Optional[callable] = None,
    ) -> None:
        """
        Generate a title asynchronously (non-blocking).
        The title is generated in the background and cached for later retrieval.
        This method returns immediately without waiting for title generation.

        Args:
            session_id: The session identifier
            user_message: The user's first message
            agent_response: The agent's response
            user_id: The user identifier
            update_callback: Optional callback to update session name after generation
        """
        log.info(f"Starting async title generation for session {session_id}")
        log.debug(f"User message: {user_message[:100]}...")
        log.debug(f"Agent response: {agent_response[:100]}...")
        
        # Fire and forget - don't await
        task = asyncio.create_task(
            self._generate_and_update_title(
                session_id=session_id,
                user_message=user_message,
                agent_response=agent_response,
                update_callback=update_callback,
            )
        )
        # Add done callback to log any exceptions
        task.add_done_callback(lambda t: self._log_task_exception(t, session_id))
        log.info(f"Async title generation task created for session {session_id}")
    
    def _log_task_exception(self, task: asyncio.Task, session_id: str) -> None:
        """Log any exceptions from the async task."""
        try:
            task.result()
        except Exception as e:
            log.error(f"Exception in async title generation task for session {session_id}: {e}", exc_info=True)

    async def _generate_and_update_title(
        self,
        session_id: str,
        user_message: str,
        agent_response: str,
        update_callback: Optional[callable] = None,
    ) -> None:
        """Internal method to generate title and update session."""
        log.info(f"[_generate_and_update_title] Starting for session {session_id}")
        
        try:
            # Generate title via LiteLLM
            log.info(f"[_generate_and_update_title] Calling LiteLLM for session {session_id}")
            title = await self._call_litellm(user_message, agent_response)
            
            log.info(f"[_generate_and_update_title] Generated title for session {session_id}: '{title}'")
            
            # Call update callback to save title to database
            if update_callback:
                try:
                    await update_callback(title)
                    log.info(f"[_generate_and_update_title] Session name updated via callback for session {session_id}")
                except Exception as e:
                    log.error(f"[_generate_and_update_title] Error calling update callback: {e}", exc_info=True)
                    
        except Exception as e:
            log.error(f"[_generate_and_update_title] Error in async title generation for session {session_id}: {e}", exc_info=True)

    async def _call_litellm(
        self,
        user_message: str,
        agent_response: str,
    ) -> str:
        """Call LiteLLM to generate title."""
        log.info(f"[_call_litellm] Starting LiteLLM call")

        # Truncate messages to avoid token limits
        user_text = self._truncate_text(user_message, MAX_USER_MESSAGE_LENGTH)
        response_text = self._truncate_text(agent_response, MAX_AGENT_RESPONSE_LENGTH)
        log.debug(f"[_call_litellm] User text (truncated): {user_text}")
        log.debug(f"[_call_litellm] Agent response (truncated): {response_text}")

        # Use a clear prompt that generates specific, meaningful titles
        prompt = f'''Generate a concise, specific title (under {TITLE_CHAR_LIMIT} characters) for this conversation.
Avoid generic titles like "New Chat" or "Conversation".
Focus on the main topic or question.

User: "{user_text}"
Agent: "{response_text}"

Title:'''

        try:
            from google.genai import types
            from google.adk.models.llm_request import LlmRequest

            llm_request = LlmRequest(
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt)],
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=DEFAULT_TEMPERATURE,
                ),
            )

            # Call LiteLLM via generate_content_async
            content = None
            async for llm_response in self.llm.generate_content_async(llm_request):
                if llm_response.content and llm_response.content.parts:
                    for part in llm_response.content.parts:
                        if part.text:
                            content = part.text
                            break
            if content is None:
                log.warning("[_call_litellm] LiteLLM returned None content, using fallback")
                return self._fallback_title(user_message)
            
            title = content.strip()

            # Remove quotes if present
            title = title.strip('"\'')

            # Ensure title is not empty
            if not title or len(title.strip()) == 0:
                log.warning("[_call_litellm] LiteLLM returned empty title, using fallback")
                return self._fallback_title(user_message)

            log.info(f"[_call_litellm] LiteLLM generated title: '{title}'")
            return title[:MAX_TITLE_LENGTH]  # Enforce max length

        except Exception as e:
            log.error(f"[_call_litellm] Error generating title via LiteLLM: {e}", exc_info=True)
            return self._fallback_title(user_message)

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to max length."""
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def _fallback_title(self, user_message: str) -> str:
        """Generate fallback title from user message."""
        if not user_message or not user_message.strip():
            return "New Chat"

        # Use first TITLE_CHAR_LIMIT chars of user message
        title = user_message.strip()[:TITLE_CHAR_LIMIT]
        if len(user_message) > TITLE_CHAR_LIMIT:
            title += "..."
        return title