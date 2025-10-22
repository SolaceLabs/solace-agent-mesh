"""
SAM Events Service - Clean system-level event messaging.

Provides event publishing and subscription for system events like session lifecycle,
agent health, configuration changes, etc.
"""

import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Callable, List

from ..a2a.protocol import get_sam_events_topic

log = logging.getLogger(__name__)

@dataclass
class SamEvent:
    """Base class for all SAM system events."""
    event_type: str
    event_id: str
    timestamp: str
    source_component: str
    namespace: str
    data: Dict[str, Any]

    @classmethod
    def create(cls, event_type: str, source_component: str, namespace: str, data: Dict[str, Any]) -> "SamEvent":
        """Create a new SAM event with auto-generated ID and timestamp."""
        return cls(
            event_type=event_type,
            event_id=uuid.uuid4().hex,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_component=source_component,
            namespace=namespace,
            data=data
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for messaging."""
        return asdict(self)


@dataclass
class SessionDeletedEvent(SamEvent):
    """System event for session deletion."""
    
    @classmethod
    def create(cls, namespace: str, source_component: str, session_id: str, 
               user_id: str, agent_id: str, gateway_id: str) -> "SessionDeletedEvent":
        """Create a session deleted event."""
        data = {
            "session_id": session_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "gateway_id": gateway_id
        }
        return super().create("session.deleted", source_component, namespace, data)


class SamEventService:
    """Service for publishing and subscribing to SAM system events."""
    
    def __init__(self, namespace: str, component_name: str, publish_func: Callable[[str, Dict, Optional[Dict]], None]):
        """
        Initialize the SAM event service.
        
        Args:
            namespace: The SAM namespace
            component_name: Name of the component using this service
            publish_func: Function to publish messages (from WebUIBackendComponent.publish_a2a)
        """
        self.namespace = namespace
        self.component_name = component_name
        self.publish_func = publish_func
        self._subscribers: Dict[str, List[Callable]] = {}
        
        log.info(f"[SamEventService] Initialized for component {component_name} in namespace {namespace}")

    def publish_event(self, event: SamEvent) -> bool:
        """
        Publish a SAM system event.
        
        Args:
            event: The system event to publish
            
        Returns:
            bool: True if published successfully, False otherwise
        """
        try:
            # Extract category and action from event_type (e.g., "session.deleted" -> "session", "deleted")
            parts = event.event_type.split(".", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid event_type format: {event.event_type}. Expected 'category.action'")
                
            category, action = parts
            topic = get_sam_events_topic(self.namespace, category, action)
            payload = event.to_dict()
            
            log.info(f"[SamEventService] Publishing {event.event_type} event (ID: {event.event_id}) to topic {topic}")
            
            # Use the component's publish function (which goes through proper A2A infrastructure)
            self.publish_func(topic, payload, {"eventType": event.event_type, "eventId": event.event_id})
            
            log.info(f"[SamEventService] Successfully published event {event.event_id}")
            return True
            
        except Exception as e:
            log.error(f"[SamEventService] Failed to publish event {event.event_id}: {e}")
            return False

    def publish_session_deleted(self, session_id: str, user_id: str, agent_id: str, gateway_id: str) -> bool:
        """
        Convenience method to publish session deleted event.
        
        Args:
            session_id: The deleted session ID
            user_id: The user who owned the session
            agent_id: The agent that was handling the session
            gateway_id: The gateway that deleted the session
            
        Returns:
            bool: True if published successfully
        """
        event = SessionDeletedEvent.create(
            namespace=self.namespace,
            source_component=self.component_name,
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            gateway_id=gateway_id
        )
        return self.publish_event(event)

    def subscribe_to_events(self, event_type: str, handler: Callable[[SamEvent], None]) -> bool:
        """
        Subscribe to system events of a specific type.
        
        Args:
            event_type: The type of events to subscribe to (e.g., "session.deleted")
            handler: Function to call when event is received
            
        Returns:
            bool: True if subscription was successful
        """
        try:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
                
            self._subscribers[event_type].append(handler)
            
            log.info(f"[SamEventService] Subscribed to {event_type} events")
            return True
            
        except Exception as e:
            log.error(f"[SamEventService] Failed to subscribe to {event_type} events: {e}")
            return False

    def handle_incoming_event(self, topic: str, payload: Dict[str, Any]) -> None:
        """
        Handle incoming SAM event from messaging system.
        
        Args:
            topic: The topic the event was received on
            payload: Event payload
        """
        try:
            event_type = payload.get("event_type")
            
            if not event_type:
                log.warning(f"[SamEventService] Received event without event_type on topic {topic}")
                return
                
            # Create event object
            event = SamEvent(**payload)
            
            # Call registered handlers
            handlers = self._subscribers.get(event_type, [])
            for handler in handlers:
                try:
                    handler(event)
                except Exception as e:
                    log.error(f"[SamEventService] Error in event handler for {event_type}: {e}")
                    
            log.debug(f"[SamEventService] Processed event {event.event_id} with {len(handlers)} handlers")
            
        except Exception as e:
            log.error(f"[SamEventService] Error handling event from topic {topic}: {e}")

    @staticmethod
    def get_event_topic(namespace: str, event_type: str) -> str:
        """
        Get the topic for a specific event type.
        
        Args:
            namespace: The SAM namespace  
            event_type: Event type in format "category.action"
            
        Returns:
            str: The topic for the event
        """
        parts = event_type.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid event_type format: {event_type}. Expected 'category.action'")
            
        category, action = parts
        return get_sam_events_topic(namespace, category, action)
