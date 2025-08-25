"""
Message handling for the development Solace broker simulator.
Manages message storage, retrieval, and lifecycle.
"""

import time
import threading
import uuid
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import deque
import logging


@dataclass
class BrokerMessage:
    """Represents a message in the broker."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    payload: Any = None
    user_properties: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    ttl_seconds: Optional[int] = None
    qos: int = 1
    
    @property
    def is_expired(self) -> bool:
        """Check if the message has expired."""
        if self.ttl_seconds is None:
            return False
        return time.time() > (self.timestamp + self.ttl_seconds)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        return {
            "id": self.id,
            "topic": self.topic,
            "payload": self.payload,
            "user_properties": self.user_properties,
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
            "qos": self.qos,
        }


class MessageHandler:
    """Handles message storage, retrieval, and lifecycle management."""
    
    def __init__(self, max_queue_size: int = 1000, default_ttl_seconds: int = 300):
        self.max_queue_size = max_queue_size
        self.default_ttl_seconds = default_ttl_seconds
        
        # Message storage
        self._messages: deque = deque(maxlen=max_queue_size)
        self._message_index: Dict[str, BrokerMessage] = {}
        
        # Message capture for testing
        self._captured_messages: List[BrokerMessage] = []
        self._capture_enabled = True
        
        # Threading
        self._lock = threading.RLock()
        self._logger = logging.getLogger(f"{__name__}.MessageHandler")
        
        # Message listeners for testing
        self._message_listeners: List[Callable[[BrokerMessage], None]] = []
    
    def store_message(
        self, 
        topic: str, 
        payload: Any, 
        user_properties: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
        qos: int = 1
    ) -> BrokerMessage:
        """
        Store a message in the broker.
        
        Args:
            topic: Message topic
            payload: Message payload
            user_properties: Optional user properties
            ttl_seconds: Time to live in seconds
            qos: Quality of service level
            
        Returns:
            The stored message
        """
        with self._lock:
            message = BrokerMessage(
                topic=topic,
                payload=payload,
                user_properties=user_properties or {},
                ttl_seconds=ttl_seconds or self.default_ttl_seconds,
                qos=qos
            )
            
            # Add to storage
            self._messages.append(message)
            self._message_index[message.id] = message
            
            # Capture for testing if enabled
            if self._capture_enabled:
                self._captured_messages.append(message)
            
            # Notify listeners
            for listener in self._message_listeners:
                try:
                    listener(message)
                except Exception as e:
                    self._logger.error(f"Error in message listener: {e}")
            
            self._logger.debug(
                f"Stored message {message.id} on topic '{topic}' "
                f"(payload size: {len(str(payload))} chars)"
            )
            
            return message
    
    def get_message(self, message_id: str) -> Optional[BrokerMessage]:
        """
        Retrieve a message by ID.
        
        Args:
            message_id: Message identifier
            
        Returns:
            The message if found and not expired, None otherwise
        """
        with self._lock:
            message = self._message_index.get(message_id)
            if message and not message.is_expired:
                return message
            return None
    
    def get_messages_by_topic(self, topic: str, limit: Optional[int] = None) -> List[BrokerMessage]:
        """
        Get messages for a specific topic.
        
        Args:
            topic: Topic to search for
            limit: Maximum number of messages to return
            
        Returns:
            List of messages for the topic
        """
        with self._lock:
            messages = []
            count = 0
            
            for message in reversed(self._messages):
                if message.is_expired:
                    continue
                    
                if message.topic == topic:
                    messages.append(message)
                    count += 1
                    
                    if limit and count >= limit:
                        break
            
            return messages
    
    def get_recent_messages(self, limit: int = 10) -> List[BrokerMessage]:
        """
        Get the most recent messages.
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages
        """
        with self._lock:
            messages = []
            count = 0
            
            for message in reversed(self._messages):
                if not message.is_expired:
                    messages.append(message)
                    count += 1
                    
                    if count >= limit:
                        break
            
            return messages
    
    def cleanup_expired_messages(self) -> int:
        """
        Remove expired messages from storage.
        
        Returns:
            Number of messages removed
        """
        with self._lock:
            removed_count = 0
            messages_to_remove = []
            
            for message in self._messages:
                if message.is_expired:
                    messages_to_remove.append(message)
            
            for message in messages_to_remove:
                self._messages.remove(message)
                if message.id in self._message_index:
                    del self._message_index[message.id]
                removed_count += 1
            
            if removed_count > 0:
                self._logger.debug(f"Cleaned up {removed_count} expired messages")
            
            return removed_count
    
    def clear_all_messages(self) -> int:
        """
        Clear all stored messages.
        
        Returns:
            Number of messages cleared
        """
        with self._lock:
            count = len(self._messages)
            self._messages.clear()
            self._message_index.clear()
            
            if count > 0:
                self._logger.info(f"Cleared all {count} messages")
            
            return count
    
    def get_message_count(self) -> int:
        """Get the current number of stored messages."""
        with self._lock:
            return len(self._messages)
    
    # Testing utilities
    
    def get_captured_messages(self) -> List[BrokerMessage]:
        """Get all captured messages for testing."""
        with self._lock:
            return self._captured_messages.copy()
    
    def clear_captured_messages(self) -> None:
        """Clear captured messages."""
        with self._lock:
            self._captured_messages.clear()
            self._logger.debug("Cleared captured messages")
    
    def set_capture_enabled(self, enabled: bool) -> None:
        """Enable or disable message capture."""
        with self._lock:
            self._capture_enabled = enabled
            self._logger.debug(f"Message capture {'enabled' if enabled else 'disabled'}")
    
    def add_message_listener(self, listener: Callable[[BrokerMessage], None]) -> None:
        """Add a message listener for testing."""
        with self._lock:
            self._message_listeners.append(listener)
            self._logger.debug("Added message listener")
    
    def remove_message_listener(self, listener: Callable[[BrokerMessage], None]) -> None:
        """Remove a message listener."""
        with self._lock:
            if listener in self._message_listeners:
                self._message_listeners.remove(listener)
                self._logger.debug("Removed message listener")
    
    def clear_message_listeners(self) -> None:
        """Clear all message listeners."""
        with self._lock:
            count = len(self._message_listeners)
            self._message_listeners.clear()
            if count > 0:
                self._logger.debug(f"Cleared {count} message listeners")
    
    def find_messages_by_payload(self, payload_filter: Callable[[Any], bool]) -> List[BrokerMessage]:
        """
        Find messages by payload content.
        
        Args:
            payload_filter: Function that returns True for matching payloads
            
        Returns:
            List of matching messages
        """
        with self._lock:
            matching_messages = []
            
            for message in self._messages:
                if message.is_expired:
                    continue
                    
                try:
                    if payload_filter(message.payload):
                        matching_messages.append(message)
                except Exception as e:
                    self._logger.debug(f"Error in payload filter: {e}")
            
            return matching_messages
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get message handler statistics."""
        with self._lock:
            total_messages = len(self._messages)
            expired_count = sum(1 for msg in self._messages if msg.is_expired)
            
            return {
                "total_messages": total_messages,
                "active_messages": total_messages - expired_count,
                "expired_messages": expired_count,
                "captured_messages": len(self._captured_messages),
                "message_listeners": len(self._message_listeners),
                "capture_enabled": self._capture_enabled,
                "max_queue_size": self.max_queue_size,
                "default_ttl_seconds": self.default_ttl_seconds,
            }
