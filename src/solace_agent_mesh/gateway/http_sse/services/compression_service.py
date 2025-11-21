"""
Compression service for conversation context compression.
Handles LLM-based summarization of conversation history.
"""

import os
import uuid
import asyncio
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime, timezone

from solace_ai_connector.common.log import log

from ..repository import ISessionRepository, Session
from ..shared.types import SessionId, UserId

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent

# Import OpenAI, Anthropic, and Google Gemini for direct LLM calls
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    log.warning("openai not available, OpenAI LLM summarization will be disabled")

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    log.warning("anthropic not available, Anthropic LLM summarization will be disabled")

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    log.warning("google-generativeai not available, Gemini LLM summarization will be disabled")


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
    ) -> CompressionResult:
        """
        Compress a conversation by generating an LLM summary.
        
        Args:
            messages: List of message dictionaries to compress
            session: The session being compressed
            user_id: The user requesting compression
            compression_type: Type of compression (currently only "llm_summary")
            llm_provider: LLM provider to use (openai, anthropic, gemini)
            llm_model: Specific model to use
            db_session: Database session for token tracking
            
        Returns:
            CompressionResult with summary and metadata
            
        Raises:
            ValueError: If invalid parameters
        """
        log.info(
            "Starting compression for session %s (user: %s, type: %s)",
            session.id,
            user_id,
            compression_type,
        )
        
        if not messages:
            raise ValueError(f"No messages provided for compression")
        
        log.info(
            "Compressing %d messages for session %s",
            len(messages),
            session.id,
        )
        
        # Generate summary using LLM
        summary = await self._generate_llm_summary(messages, session, llm_provider, llm_model, user_id, db_session)
        
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
        
        log.info(
            "Compression complete for session %s: %d messages → %d tokens (saved ~%d tokens)",
            session.id,
            result.message_count,
            result.compressed_token_estimate,
            result.original_token_estimate - result.compressed_token_estimate,
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
    ) -> str:
        """
        Generate an LLM-based summary of the conversation.
        
        Uses a hybrid approach:
        1. Try to call the same agent/LLM used in the conversation for intelligent summarization
        2. Fall back to structured summary if LLM call fails
        
        Args:
            messages: List of message dictionaries to summarize
            session: The session being compressed
            llm_provider: Provider to use
            llm_model: Model to use
            user_id: User ID for token tracking
            db_session: Database session for token tracking
            
        Returns:
            Summary text
        """
        
        # Try LLM-based summarization first
        if self.component and session.agent_id:
            try:
                llm_summary = await self._call_llm_for_summary(messages, session, llm_provider, llm_model, user_id, db_session)
                if llm_summary:
                    log.info(
                        "Successfully generated LLM summary for session %s (%d chars)",
                        session.id,
                        len(llm_summary),
                    )
                    return llm_summary
            except Exception as e:
                log.warning(
                    "LLM summarization failed for session %s, falling back to structured summary: %s",
                    session.id,
                    e,
                )
        
        # Fall back to structured summary
        log.info("Using structured summary for session %s", session.id)
        return self._create_structured_summary(messages, session)
    
    async def _call_llm_for_summary(
        self,
        messages: List[Dict[str, Any]],
        session: Session,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        user_id: str | None = None,
        db_session = None,
    ) -> Optional[str]:
        """
        Call LLM API (OpenAI, Anthropic, or Gemini) for intelligent summarization.
        
        Args:
            messages: List of messages to summarize
            session: The session being compressed
            llm_provider: Provider to use ('openai', 'anthropic', or 'gemini')
            llm_model: Model to use
            
        Returns:
            LLM-generated summary or None if call fails
        """
        # Determine provider (default to openai)
        provider = llm_provider or "openai"
        
        if provider == "anthropic":
            return await self._call_anthropic_for_summary(messages, session, llm_model, user_id, db_session)
        elif provider == "gemini":
            return await self._call_gemini_for_summary(messages, session, llm_model, user_id, db_session)
        else:
            return await self._call_openai_for_summary(messages, session, llm_model, user_id, db_session)
    
    async def _call_openai_for_summary(
        self,
        messages: List[Dict[str, Any]],
        session: Session,
        llm_model: str | None = None,
        user_id: str | None = None,
        db_session = None,
    ) -> Optional[str]:
        """Call OpenAI API for intelligent summarization."""
        if not OPENAI_AVAILABLE:
            log.info("OpenAI not available, skipping OpenAI summarization")
            return None
        
        try:
            # Get API key from environment
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                log.info("No OPENAI_API_KEY found in environment, using structured summary")
                return None
            
            # Get model name from parameter, config, or use default
            model_name = llm_model or "gpt-4o-mini"  # Default to gpt-4o-mini
            if not llm_model and self.component:
                compression_config = self.component.get_config("compression", {})
                summarization_config = compression_config.get("summarization", {})
                model_name = summarization_config.get("model", model_name)
            
            log.info(
                "Using OpenAI model '%s' for summarization of session %s",
                model_name,
                session.id,
            )
            
            # Initialize OpenAI client
            client = AsyncOpenAI(api_key=api_key)
            
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
            
            # Call OpenAI API
            log.debug("Calling OpenAI API for summarization (model: %s)", model_name)
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for consistent summaries
                max_tokens=1000,
            )
            
            # Extract summary text
            if response and response.choices and len(response.choices) > 0:
                summary_text = response.choices[0].message.content.strip()
                
                # Track token usage
                if response.usage and user_id and db_session:
                    try:
                        from .usage_tracking_service import UsageTrackingService
                        usage_service = UsageTrackingService(db_session)
                        usage_service.record_token_usage(
                            user_id=user_id,
                            task_id=None,
                            model=model_name,
                            prompt_tokens=response.usage.prompt_tokens,
                            completion_tokens=response.usage.completion_tokens,
                            cached_input_tokens=getattr(response.usage, 'prompt_tokens_details', {}).get('cached_tokens', 0) if hasattr(response.usage, 'prompt_tokens_details') else 0,
                            source="compression",
                            context=f"Session compression: {session.id}",
                        )
                        log.info("Tracked compression token usage: %d tokens", response.usage.total_tokens)
                    except Exception as e:
                        log.warning("Failed to track compression token usage: %s", e)
                
                tokens_used = response.usage.total_tokens if response.usage else 0
                log.info(
                    "Successfully generated OpenAI summary for session %s (%d chars, %d tokens used)",
                    session.id,
                    len(summary_text),
                    tokens_used,
                )
                return summary_text
            
            log.warning("OpenAI response did not contain text")
            return None
            
        except Exception as e:
            log.warning("OpenAI summarization failed: %s", e)
            return None
    
    async def _call_anthropic_for_summary(
        self,
        messages: List[Dict[str, Any]],
        session: Session,
        llm_model: str | None = None,
        user_id: str | None = None,
        db_session = None,
    ) -> Optional[str]:
        """Call Anthropic API for intelligent summarization."""
        if not ANTHROPIC_AVAILABLE:
            log.info("Anthropic not available, skipping Anthropic summarization")
            return None
        
        try:
            # Get API key from environment
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                log.info("No ANTHROPIC_API_KEY found in environment, using structured summary")
                return None
            
            # Get model name from parameter or use default
            model_name = llm_model or "claude-3-5-sonnet-20241022"
            if not llm_model and self.component:
                compression_config = self.component.get_config("compression", {})
                summarization_config = compression_config.get("summarization", {})
                model_name = summarization_config.get("anthropic_model", model_name)
            
            log.info(
                "Using Anthropic model '%s' for summarization of session %s",
                model_name,
                session.id,
            )
            
            # Initialize Anthropic client
            client = AsyncAnthropic(api_key=api_key)
            
            # Build conversation text
            conversation_text = self._build_conversation_text(messages)
            
            # Create summarization prompt
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
            
            # Call Anthropic API
            log.debug("Calling Anthropic API for summarization (model: %s)", model_name)
            response = await client.messages.create(
                model=model_name,
                max_tokens=1000,
                temperature=0.3,  # Lower temperature for consistent summaries
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
            )
            
            # Extract summary text
            if response and response.content and len(response.content) > 0:
                summary_text = response.content[0].text.strip()
                
                # Track token usage
                if response.usage and user_id and db_session:
                    try:
                        from .usage_tracking_service import UsageTrackingService
                        usage_service = UsageTrackingService(db_session)
                        usage_service.record_token_usage(
                            user_id=user_id,
                            task_id=None,
                            model=model_name,
                            prompt_tokens=response.usage.input_tokens,
                            completion_tokens=response.usage.output_tokens,
                            cached_input_tokens=getattr(response.usage, 'cache_read_input_tokens', 0),
                            source="compression",
                            context=f"Session compression: {session.id}",
                        )
                        log.info("Tracked compression token usage: %d tokens", response.usage.input_tokens + response.usage.output_tokens)
                    except Exception as e:
                        log.warning("Failed to track compression token usage: %s", e)
                
                tokens_used = response.usage.input_tokens + response.usage.output_tokens if response.usage else 0
                log.info(
                    "Successfully generated Anthropic summary for session %s (%d chars, %d tokens used)",
                    session.id,
                    len(summary_text),
                    tokens_used,
                )
                return summary_text
            
            log.warning("Anthropic response did not contain text")
            return None
            
        except Exception as e:
            log.warning("Anthropic summarization failed: %s", e)
            return None
    
    async def _call_gemini_for_summary(
        self,
        messages: List[Dict[str, Any]],
        session: Session,
        llm_model: str | None = None,
        user_id: str | None = None,
        db_session = None,
    ) -> Optional[str]:
        """Call Google Gemini API for intelligent summarization."""
        if not GEMINI_AVAILABLE:
            log.info("Gemini not available, skipping Gemini summarization")
            return None
        
        try:
            # Get API key from environment
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                log.info("No GEMINI_API_KEY or GOOGLE_API_KEY found in environment, using structured summary")
                return None
            
            # Configure Gemini
            genai.configure(api_key=api_key)
            
            # Get model name from parameter or use default
            model_name = llm_model or "gemini-1.5-flash"
            if not llm_model and self.component:
                compression_config = self.component.get_config("compression", {})
                summarization_config = compression_config.get("summarization", {})
                model_name = summarization_config.get("gemini_model", model_name)
            
            log.info(
                "Using Gemini model '%s' for summarization of session %s",
                model_name,
                session.id,
            )
            
            # Initialize Gemini model
            model = genai.GenerativeModel(model_name)
            
            # Build conversation text
            conversation_text = self._build_conversation_text(messages)
            
            # Create summarization prompt
            prompt = f"""You are a conversation summarization assistant. Create concise but comprehensive summaries of conversations.

IMPORTANT INSTRUCTIONS:
1. Preserve all key information, decisions, and outcomes
2. Maintain chronological flow of the conversation
3. Include specific details about files, artifacts, or code created
4. Capture the main topics and subtopics discussed
5. Note any unresolved questions or pending tasks
6. Keep the summary under 1000 tokens while being thorough
7. Use clear, structured formatting with headers and bullet points
8. Focus on actionable information and context needed for continuation
9. DO NOT include metadata like dates, session names, or message counts - focus only on the conversation content

Please summarize the following conversation. Focus on the content and context, not metadata:

{conversation_text}"""
            
            # Call Gemini API
            log.debug("Calling Gemini API for summarization (model: %s)", model_name)
            
            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=0.3,  # Lower temperature for consistent summaries
                max_output_tokens=1000,
            )
            
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=generation_config
            )
            
            # Extract summary text
            if response and response.text:
                summary_text = response.text.strip()
                log.info(
                    "Successfully generated Gemini summary for session %s (%d chars)",
                    session.id,
                    len(summary_text),
                )
                return summary_text
            
            log.warning("Gemini response did not contain text")
            return None
            
        except Exception as e:
            log.warning("Gemini summarization failed: %s", e)
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