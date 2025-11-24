"""
Compression service for conversation context compression.
Handles LLM-based summarization of conversation history.
"""

import json
import uuid
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime, timezone

from solace_ai_connector.common.log import log

from ..repository import ISessionRepository, Session
from ..repository.models.chat_task_model import ChatTaskModel
from ..shared import now_epoch_ms
from ..shared.types import SessionId, UserId

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent


class CompressionConfigError(Exception):
    """Raised when LLM configuration is missing for compression."""
    pass


class CompressionResult:
    """Result of a compression operation."""
    
    def __init__(
        self,
        compression_id: str,
        summary: str,
        message_count: int,
        original_token_estimate: int,
        compressed_token_estimate: int,
        artifacts_metadata: List[Dict[str, Any]],
        compression_timestamp: int,
    ):
        self.compression_id = compression_id
        self.summary = summary
        self.message_count = message_count
        self.original_token_estimate = original_token_estimate
        self.compressed_token_estimate = compressed_token_estimate
        self.artifacts_metadata = artifacts_metadata
        self.compression_timestamp = compression_timestamp


class CompressionService:
    """Service for compressing conversation context using LLM summarization."""
    
    def __init__(
        self,
        session_repository: ISessionRepository,
        component: Optional["WebUIBackendComponent"] = None,
    ):
        self.session_repository = session_repository
        self.component = component
    
    async def compress_conversation(
        self,
        messages: List[Dict[str, Any]],
        session: Session,
        user_id: UserId,
        compression_type: str = "llm_summary",
        llm_provider: str | None = None,
        llm_model: str | None = None,
        db_session = None,
        target_session_id: str | None = None,
    ) -> CompressionResult:
        """
        Compress a conversation by generating an LLM summary.
        
        Args:
            messages: List of message dictionaries to compress
            session: The session being compressed (source session)
            user_id: The user requesting compression
            compression_type: Type of compression (currently only "llm_summary")
            llm_provider: LLM provider to use (openai, anthropic, gemini)
            llm_model: Specific model to use
            db_session: Database session for token tracking
            target_session_id: Optional session ID where compression task should be tracked
                              (defaults to None, which means no task tracking)
            
        Returns:
            CompressionResult with summary and metadata
            
        Raises:
            ValueError: If invalid parameters
        """
   
        
        if not messages:
            raise ValueError(f"No messages provided for compression")
        
       
        
        # Generate summary using LLM
        summary = await self._generate_llm_summary(
            messages, session, llm_provider, llm_model, user_id, db_session, target_session_id
        )
        
        # Extract artifact metadata
        artifacts_metadata = self._extract_artifacts_metadata(messages)
        
        # Estimate token counts (rough approximation: 1 token ≈ 4 characters)
        original_text = "\n".join(msg.get("message", "") for msg in messages)
        original_token_estimate = len(original_text) // 4
        compressed_token_estimate = len(summary) // 4
        
        compression_id = str(uuid.uuid4())
        compression_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        result = CompressionResult(
            compression_id=compression_id,
            summary=summary,
            message_count=len(messages),
            original_token_estimate=original_token_estimate,
            compressed_token_estimate=compressed_token_estimate,
            artifacts_metadata=artifacts_metadata,
            compression_timestamp=compression_timestamp,
        )
        
        
        return result
    
    async def _generate_llm_summary(
        self,
        messages: List[Dict[str, Any]],
        session: Session,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        user_id: str | None = None,
        db_session = None,
        target_session_id: str | None = None,
    ) -> str:
        """
        Generate an LLM-based summary of the conversation.
        
        Uses a hybrid approach:
        1. Try to call the same agent/LLM used in the conversation for intelligent summarization
        2. Fall back to structured summary if LLM call fails
        
        Args:
            messages: List of message dictionaries to summarize
            session: The session being compressed (source session)
            llm_provider: Provider to use
            llm_model: Model to use
            user_id: User ID for token tracking
            db_session: Database session for token tracking
            target_session_id: Optional session ID where compression task should be tracked
            
        Returns:
            Summary text
        """
        
        # Try LLM-based summarization first
        if self.component and session.agent_id:
            try:
                llm_summary = await self._call_llm_for_summary(
                    messages, session, llm_provider, llm_model, user_id, db_session, target_session_id
                )
                if llm_summary:
                  
                    return llm_summary
            except Exception as e:
                log.warning(
                    "LLM summarization failed for session %s, falling back to structured summary: %s",
                    session.id,
                    e,
                )
        
        # Fall back to structured summary
        return self._create_structured_summary(messages, session)
    
    async def _call_llm_for_summary(
        self,
        messages: List[Dict[str, Any]],
        session: Session,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        user_id: str | None = None,
        db_session = None,
        target_session_id: str | None = None,
    ) -> Optional[str]:
        """
        Call LLM via LiteLLM for intelligent summarization.
        
        Args:
            messages: List of messages to summarize
            session: The session being compressed (source session)
            llm_provider: Provider to use (ignored, uses component's model config)
            llm_model: Model to use (overrides component's model config if provided)
            user_id: User ID for token tracking
            db_session: Database session for token tracking
            target_session_id: Optional session ID where compression task should be tracked
            
        Returns:
            LLM-generated summary or None if call fails
        """
        if not self.component:
            log.warning("Component not available for LLM summarization")
            return None
        
        try:
            # Get model configuration from component
            model_config = self.component.get_config("model", {})
                
            if not model_config:
                raise CompressionConfigError(
                    "LLM configuration required for compression. Please configure 'model' "
                    "in your gateway configuration."
                )
            
            # Import LiteLLM here to avoid circular imports
            from ....agent.adk.models.lite_llm import LiteLlm
            
            # Determine the model to use
            if llm_model:
                # Override with provided model
                llm_instance = LiteLlm(model=llm_model)
            elif isinstance(model_config, dict):
                # Extract model string and other config separately
                if not model_config.get("model"):
                    raise CompressionConfigError(
                        "Model name not found in model configuration. Please specify 'model' "
                        "in your gateway's model configuration."
                    )
                
                # Extract the model string (keep provider prefix intact)
                model_string = model_config["model"]
                
                # Extract api_base, api_key, and cache_strategy separately
                # These need to be passed as kwargs to LiteLlm constructor to match agent behavior
                api_base = model_config.get("api_base")
                api_key = model_config.get("api_key")
                cache_strategy = model_config.get("cache_strategy", "5m")
                
                # Build kwargs for LiteLlm constructor
                llm_kwargs = {}
                if api_base:
                    llm_kwargs["api_base"] = api_base
                if api_key:
                    llm_kwargs["api_key"] = api_key
                
                # Pass model and additional args like agents do
                # This ensures api_base and api_key are in _additional_args
                llm_instance = LiteLlm(model=model_string, cache_strategy=cache_strategy, **llm_kwargs)
            elif isinstance(model_config, str):
                llm_instance = LiteLlm(model=model_config)
            else:
                raise CompressionConfigError(
                    f"Invalid model configuration type: {type(model_config)}"
                )
            
            # Always use the model string from the LiteLlm instance
            # This ensures we use the exact same model string that was configured,
            # with the provider prefix intact
            model_name = llm_instance.model
            
    
            # Build conversation text
            conversation_text = self._build_conversation_text(messages)
            
            # Create summarization prompts
            system_prompt = """You are a conversation summarization assistant. Create concise but comprehensive summaries of conversations.

IMPORTANT INSTRUCTIONS:
1. Preserve all key information, decisions, and outcomes
2. Maintain chronological flow of the conversation
3. Include specific details about files, artifacts, or code created
4. Capture the main topics and subtopics discussed
5. Note any unresolved questions or pending tasks
6. Keep the summary under 1000 tokens while being thorough
7. Use clear, structured formatting with headers and bullet points
8. Focus on actionable information and context needed for continuation
9. DO NOT include metadata like dates, session names, or message counts - focus only on the conversation content"""
            
            user_prompt = f"""Please summarize the following conversation. Focus on the content and context, not metadata:

{conversation_text}"""
            
            # Prepare messages using google.genai types for LlmRequest
            from google.genai import types
            from google.adk.models.llm_request import LlmRequest
            
            # Build LlmRequest with system instruction and user message
            llm_request = LlmRequest(
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=user_prompt)]
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                    max_output_tokens=1000,
                )
            )
            
            # Call generate_content_async which properly merges _additional_args
            # This ensures api_base and api_key are included in the request
            log.debug("Calling generate_content_async for summarization (model: %s)", model_name)
            
            try:
                # generate_content_async returns an async generator, get first response
                response_generator = llm_instance.generate_content_async(llm_request, stream=False)
                llm_response = None
                async for response_chunk in response_generator:
                    llm_response = response_chunk
                    break  # We only need the first (and only) response for non-streaming
                
                if not llm_response:
                    log.warning("No response received from generate_content_async")
                    return None
            except Exception as e:
                log.error("=== generate_content_async Exception Details ===")
                log.error("Exception type: %s", type(e).__name__)
                log.error("Exception message: %s", str(e))
                log.error("Model: %s", model_name)
                log.error("llm_instance._additional_args: %s", getattr(llm_instance, '_additional_args', 'N/A'))
                
                # Log the full exception with traceback
                import traceback
                log.error("Full exception traceback:")
                log.error(traceback.format_exc())
                log.error("=== End generate_content_async Exception Details ===")
                raise
            
            # Extract summary text from LlmResponse
            if llm_response and llm_response.content and llm_response.content.parts:
                # Get text from the first part
                summary_text = None
                for part in llm_response.content.parts:
                    if part.text:
                        summary_text = part.text.strip()
                        break
                
                if summary_text:
                    # Track token usage only if target_session_id is provided
                    # This ensures compression tokens are tracked in the NEW compressed session,
                    # not the original session being compressed
                    if llm_response.usage_metadata and user_id and db_session and target_session_id:
                        try:
                            # Create a system task for compression tracking in the TARGET session
                            task_id = str(uuid.uuid4())
                            compression_task = ChatTaskModel(
                                id=task_id,
                                session_id=target_session_id,  # Track in the NEW compressed session
                                user_id=user_id,
                                user_message="System: Context Compression",
                                message_bubbles=json.dumps([]),
                                task_metadata=json.dumps({
                                    "type": "compression",
                                    "provider": "litellm",
                                    "source_session_id": session.id  # Reference to original session
                                }),
                                created_time=now_epoch_ms(),
                                updated_time=now_epoch_ms()
                            )
                            db_session.add(compression_task)
                            db_session.flush()

                            from .usage_tracking_service import UsageTrackingService
                            usage_service = UsageTrackingService(db_session)
                            
                            usage_metadata = llm_response.usage_metadata
                            usage_service.record_token_usage(
                                user_id=user_id,
                                task_id=task_id,
                                model=model_name,
                                prompt_tokens=usage_metadata.prompt_token_count,
                                completion_tokens=usage_metadata.candidates_token_count,
                                cached_input_tokens=0,  # LlmResponse doesn't expose cached tokens separately
                                source="compression",
                                context=f"Session compression: {session.id} -> {target_session_id}",
                            )
                        except Exception as e:
                            log.warning("Failed to track compression token usage: %s", e)
                    
                    return summary_text
            
            log.warning("generate_content_async response did not contain text")
            return None
            
        except CompressionConfigError:
            # Re-raise configuration errors
            raise
        except Exception as e:
            log.warning("LiteLLM summarization failed: %s", e)
            return None
    
    
    def _create_structured_summary(
        self,
        messages: List[Dict[str, Any]],
        session: Session,
    ) -> str:
        """
        Create a structured summary without LLM (fallback method).
        
        Args:
            messages: List of messages to summarize
            session: The session being compressed
            
        Returns:
            Structured summary text
        """
        
        # Build conversation text
        conversation_parts = []
        for msg in messages:
            sender = "User" if msg.get("sender_type") == "user" else msg.get("sender_name", "Assistant")
            conversation_parts.append(f"{sender}: {msg.get('message', '')[:200]}...")
        
        # Create structured summary
        summary_parts = [
            "## Conversation Summary",
            "",
            f"**Session**: {session.name or 'Untitled Chat'}",
            f"**Messages**: {len(messages)}",
            f"**Participants**: User and AI Assistant",
            "",
            "### Key Points",
            "",
        ]
        
        # Extract key topics from messages (simple keyword extraction)
        topics = self._extract_topics(messages)
        if topics:
            for topic in topics[:5]:  # Top 5 topics
                summary_parts.append(f"- {topic}")
        else:
            summary_parts.append("- General conversation")
        
        summary_parts.extend([
            "",
            "### Conversation Flow",
            "",
        ])
        
        # Add first and last few exchanges
        if len(messages) > 6:
            # First 3 messages
            for msg in messages[:3]:
                sender = "User" if msg.get("sender_type") == "user" else "Assistant"
                preview = msg.get("message", "")[:100].replace("\n", " ")
                summary_parts.append(f"**{sender}**: {preview}...")
            
            summary_parts.append("")
            summary_parts.append(f"*[{len(messages) - 6} messages omitted]*")
            summary_parts.append("")
            
            # Last 3 messages
            for msg in messages[-3:]:
                sender = "User" if msg.get("sender_type") == "user" else "Assistant"
                preview = msg.get("message", "")[:100].replace("\n", " ")
                summary_parts.append(f"**{sender}**: {preview}...")
        else:
            # Include all messages if there are few
            for msg in messages:
                sender = "User" if msg.get("sender_type") == "user" else "Assistant"
                preview = msg.get("message", "")[:150].replace("\n", " ")
                summary_parts.append(f"**{sender}**: {preview}...")
        
        return "\n".join(summary_parts)
    
    def _build_conversation_text(self, messages: List[Dict[str, Any]]) -> str:
        """
        Build formatted conversation text for LLM summarization.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Formatted conversation text
        """
        conversation_lines = []
        for i, msg in enumerate(messages, 1):
            sender = "User" if msg.get("sender_type") == "user" else "Assistant"
            conversation_lines.append(f"[Message {i}] {sender}:")
            conversation_lines.append(msg.get("message", ""))
            conversation_lines.append("")  # Blank line between messages
        
        return "\n".join(conversation_lines)
    
    def _extract_topics(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        Extract key topics from messages using simple keyword analysis.
        
        Args:
            messages: List of message dictionaries to analyze
            
        Returns:
            List of topic strings
        """
        # Simple topic extraction based on common technical terms
        topics = set()
        
        # Common technical keywords to look for
        keywords = {
            "code": "Code implementation",
            "bug": "Bug fixing",
            "error": "Error resolution",
            "feature": "Feature development",
            "test": "Testing",
            "deploy": "Deployment",
            "database": "Database operations",
            "api": "API development",
            "frontend": "Frontend development",
            "backend": "Backend development",
            "design": "Design discussion",
            "architecture": "Architecture planning",
            "performance": "Performance optimization",
            "security": "Security considerations",
            "documentation": "Documentation",
        }
        
        # Check messages for keywords
        all_text = " ".join(msg.get("message", "").lower() for msg in messages)
        for keyword, topic in keywords.items():
            if keyword in all_text:
                topics.add(topic)
        
        return sorted(list(topics))
    
    def _extract_artifacts_metadata(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Extract metadata about artifacts created during the conversation.
        
        Args:
            messages: List of message dictionaries to analyze
            
        Returns:
            List of artifact metadata dictionaries
        """
        artifacts = []
        
        for msg in messages:
            artifact_notification = msg.get("artifact_notification")
            if artifact_notification:
                artifact_info = {
                    "filename": artifact_notification.get("name", "Unknown"),
                    "type": artifact_notification.get("mime_type", "unknown"),
                    "message_id": msg.get("id"),
                }
                artifacts.append(artifact_info)
        
        return artifacts