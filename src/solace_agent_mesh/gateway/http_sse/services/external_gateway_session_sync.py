"""
Service for creating and syncing sessions for external gateways (Slack, Teams, etc.).

This service enables conversations from external gateways to be persisted and displayed
in the web UI by creating corresponding session records in the database.
"""

import hashlib
import logging
import re
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session as DBSession

from ..repository.entities import Session
from ..repository.session_repository import SessionRepository
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

log = logging.getLogger(__name__)


class ExternalGatewaySessionSync:
    """
    Service to create/sync sessions for external gateways like Slack and Teams.
    
    This service handles:
    - Parsing external context IDs to extract gateway type and metadata
    - Creating normalized session IDs for external gateways
    - Creating session records in the database for external gateway conversations
    """

    # Known gateway prefixes and their patterns
    GATEWAY_PATTERNS = {
        "slack": re.compile(r"^slack_([^_]+)__(\d+)(?:_\d+)?(?:_agent_(.+))?$"),
        "teams": re.compile(r"^teams_([^_]+)__(\d+)(?:_\d+)?(?:_agent_(.+))?$"),
        "web": re.compile(r"^web-session-(.+)$"),
    }

    def __init__(self):
        self.session_repository = SessionRepository()
        self.log_identifier = "[ExternalGatewaySessionSync]"

    def parse_external_context_id(self, context_id: str) -> Dict[str, Optional[str]]:
        """
        Parse external context ID to extract gateway type and metadata.
        
        Args:
            context_id: The context ID from the A2A message
                Examples:
                - slack_D07LYGHF0BS__1741242508_413359_agent_OrchestratorAgent
                - teams_channel123__1741242508_agent_OrchestratorAgent
                - web-session-abc123def456
        
        Returns:
            Dictionary with:
            - gateway_type: 'slack', 'teams', 'web', or 'unknown'
            - channel_id: Channel/conversation ID (for Slack/Teams)
            - timestamp: Timestamp from context (for Slack/Teams)
            - agent_name: Agent name if present
            - base_context: The base context without agent suffix
        """
        result = {
            "gateway_type": "unknown",
            "channel_id": None,
            "timestamp": None,
            "agent_name": None,
            "base_context": context_id,
        }

        if not context_id:
            return result

        # Try to match against known patterns
        for gateway_type, pattern in self.GATEWAY_PATTERNS.items():
            match = pattern.match(context_id)
            if match:
                result["gateway_type"] = gateway_type
                groups = match.groups()
                
                if gateway_type == "web":
                    result["channel_id"] = groups[0]
                else:
                    result["channel_id"] = groups[0] if len(groups) > 0 else None
                    result["timestamp"] = groups[1] if len(groups) > 1 else None
                    result["agent_name"] = groups[2] if len(groups) > 2 else None
                
                # Extract base context (without agent suffix)
                if "_agent_" in context_id:
                    result["base_context"] = context_id.rsplit("_agent_", 1)[0]
                
                return result

        # Check for simple prefix-based detection
        if context_id.startswith("slack_"):
            result["gateway_type"] = "slack"
            if "_agent_" in context_id:
                result["base_context"] = context_id.rsplit("_agent_", 1)[0]
        elif context_id.startswith("teams_"):
            result["gateway_type"] = "teams"
            if "_agent_" in context_id:
                result["base_context"] = context_id.rsplit("_agent_", 1)[0]
        elif context_id.startswith("web-session-"):
            result["gateway_type"] = "web"

        return result

    def generate_session_id(self, gateway_type: str, external_context_id: str) -> str:
        """
        Generate a normalized session ID for an external gateway context.
        
        The session ID is deterministic based on the external context, so the same
        external conversation will always map to the same session ID.
        
        Args:
            gateway_type: The gateway type (slack, teams, etc.)
            external_context_id: The original external context ID
        
        Returns:
            Normalized session ID in format: {gateway_type}-session-{hash}
        """
        # Parse to get base context (without agent suffix)
        parsed = self.parse_external_context_id(external_context_id)
        base_context = parsed["base_context"]
        
        # Create a hash of the base context for a shorter, consistent ID
        context_hash = hashlib.sha256(base_context.encode()).hexdigest()[:16]
        
        return f"{gateway_type}-session-{context_hash}"

    def get_or_create_session(
        self,
        db: DBSession,
        external_context_id: str,
        user_id: str,
        gateway_type: Optional[str] = None,
    ) -> Tuple[Session, bool]:
        """
        Get existing session or create new one for external gateway context.
        
        Args:
            db: Database session
            external_context_id: The original external context ID
            user_id: User ID (may be external user ID like Slack user)
            gateway_type: Optional gateway type override (auto-detected if not provided)
        
        Returns:
            Tuple of (Session, created) where created is True if a new session was created
        """
        # Parse the context ID to determine gateway type
        parsed = self.parse_external_context_id(external_context_id)
        effective_gateway_type = gateway_type or parsed["gateway_type"]
        
        if effective_gateway_type == "web":
            # For web sessions, use the original context ID as session ID
            session_id = external_context_id
        else:
            # For external gateways, generate a normalized session ID
            session_id = self.generate_session_id(effective_gateway_type, external_context_id)
        
        # Check if session already exists
        existing_session = self.session_repository.find_by_external_context(
            db, external_context_id
        )
        
        if existing_session:
            log.debug(
                f"{self.log_identifier} Found existing session {existing_session.id} "
                f"for external context {external_context_id}"
            )
            return existing_session, False
        
        # Also check by generated session ID (for backwards compatibility)
        existing_by_id = self.session_repository.find_by_id(db, session_id)
        if existing_by_id:
            log.debug(
                f"{self.log_identifier} Found existing session by ID {session_id} "
                f"for external context {external_context_id}"
            )
            return existing_by_id, False
        
        # Create new session
        current_time = now_epoch_ms()
        
        # Generate a session name based on gateway type
        session_name = self._generate_session_name(effective_gateway_type, parsed)
        
        new_session = Session(
            id=session_id,
            user_id=user_id,
            name=session_name,
            agent_id=parsed.get("agent_name"),
            gateway_type=effective_gateway_type,
            external_context_id=external_context_id,
            created_time=current_time,
            updated_time=current_time,
        )
        
        # Save to database
        saved_session = self.session_repository.save(db, new_session)
        
        log.info(
            f"{self.log_identifier} Created new session {session_id} "
            f"for external gateway {effective_gateway_type} "
            f"(external context: {external_context_id})"
        )
        
        return saved_session, True

    def _generate_session_name(
        self, gateway_type: str, parsed_context: Dict[str, Optional[str]]
    ) -> str:
        """
        Generate a human-readable session name based on gateway type.
        
        Args:
            gateway_type: The gateway type
            parsed_context: Parsed context information
        
        Returns:
            Human-readable session name
        """
        channel_id = parsed_context.get("channel_id", "")
        
        if gateway_type == "slack":
            # Slack channel IDs start with C (channel), D (DM), or G (group)
            if channel_id.startswith("D"):
                return "Slack Direct Message"
            elif channel_id.startswith("C"):
                return f"Slack Channel"
            elif channel_id.startswith("G"):
                return "Slack Group"
            return "Slack Conversation"
        
        elif gateway_type == "teams":
            return "Teams Conversation"
        
        return f"{gateway_type.title()} Conversation"

    def is_external_gateway_context(self, context_id: str) -> bool:
        """
        Check if a context ID is from an external gateway (not web).
        
        Args:
            context_id: The context ID to check
        
        Returns:
            True if the context is from an external gateway
        """
        parsed = self.parse_external_context_id(context_id)
        return parsed["gateway_type"] not in ("web", "unknown")
