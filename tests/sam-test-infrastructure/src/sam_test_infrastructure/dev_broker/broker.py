"""
Main development Solace broker simulator for Event Mesh Gateway testing.
"""

import asyncio
import threading
import time
from typing import Dict, List, Any, Optional, Callable
import logging

from .config import BrokerConfig
from .topic_manager import TopicManager
from .message_handler import MessageHandler, BrokerMessage


class DevBroker:
    """
    Development Solace broker simulator for testing.
    
    Provides a lightweight, in-memory broker that simulates Solace PubSub+ functionality
    for testing the Event Mesh Gateway.
    """
    
    def __init__(self, config: Optional[BrokerConfig] = None):
        self.config = config or BrokerConfig()
        self._logger = logging.getLogger(f"{__name__}.DevBroker")
        
        # Core components
        self.topic_manager = TopicManager(max_subscriptions=self.config.max_subscriptions)
        self.message_handler = MessageHandler(
            max_queue_size=self.config.max_queue_size,
            default_ttl_seconds=self.config.message_ttl_seconds
        )
        
        # State management
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 30  # seconds
        
        # Client connections (for simulation)
        self._clients: Dict[str, Dict[str, Any]] = {}
        self._client_lock = threading.RLock()
        
        # Statistics
        self._stats = {
            "messages_published": 0,
            "messages_delivered": 0,
            "subscriptions_added": 0,
            "subscriptions_removed": 0,
            "clients_connected": 0,
            "clients_disconnected": 0,
            "start_time": None,
        }
        
        self._logger.info(f"DevBroker initialized on {self.config.broker_url}")
    
    async def start(self) -> None:
        """Start the broker."""
        if self._running:
            self._logger.warning("DevBroker is already running")
            return
        
        self._running = True
        self._stats["start_time"] = time.time()
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self._logger.info(f"DevBroker started on {self.config.broker_url}")
    
    async def stop(self) -> None:
        """Stop the broker."""
        if not self._running:
            self._logger.warning("DevBroker is not running")
            return
        
        self._running = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect all clients
        await self._disconnect_all_clients()
        
        # Clear all data
        self.topic_manager.clear_all_subscriptions()
        self.message_handler.clear_all_messages()
        self.message_handler.clear_captured_messages()
        self.message_handler.clear_message_listeners()
        
        self._logger.info("DevBroker stopped")
    
    def publish_message(
        self,
        topic: str,
        payload: Any,
        user_properties: Optional[Dict[str, Any]] = None,
        qos: int = 1
    ) -> BrokerMessage:
        """
        Publish a message to the broker.
        
        Args:
            topic: Message topic
            payload: Message payload
            user_properties: Optional user properties
            qos: Quality of service level
            
        Returns:
            The published message
        """
        if not self._running:
            raise RuntimeError("DevBroker is not running")
        
        # Store the message
        message = self.message_handler.store_message(
            topic=topic,
            payload=payload,
            user_properties=user_properties,
            qos=qos
        )
        
        # Route to subscribers
        delivery_count = self.topic_manager.route_message(topic, message)
        
        # Update statistics
        self._stats["messages_published"] += 1
        self._stats["messages_delivered"] += delivery_count
        
        self._logger.debug(
            f"Published message {message.id} on topic '{topic}' "
            f"(delivered to {delivery_count} subscribers)"
        )
        
        return message
    
    def subscribe(
        self,
        client_id: str,
        topic_pattern: str,
        callback: Callable[[str, BrokerMessage], None],
        qos: int = 1
    ) -> bool:
        """
        Subscribe to a topic pattern.
        
        Args:
            client_id: Client identifier
            topic_pattern: Topic pattern with optional wildcards
            callback: Function to call when matching messages arrive
            qos: Quality of service level
            
        Returns:
            True if subscription was successful, False otherwise
        """
        if not self._running:
            raise RuntimeError("DevBroker is not running")
        
        # Wrap the callback to pass the BrokerMessage
        def wrapped_callback(topic: str, message: Any) -> None:
            if isinstance(message, BrokerMessage):
                callback(topic, message)
            else:
                # Create a BrokerMessage if needed
                broker_msg = BrokerMessage(topic=topic, payload=message)
                callback(topic, broker_msg)
        
        success = self.topic_manager.add_subscription(
            subscriber_id=client_id,
            topic_pattern=topic_pattern,
            callback=wrapped_callback,
            qos=qos
        )
        
        if success:
            self._stats["subscriptions_added"] += 1
            self._logger.info(f"Client {client_id} subscribed to '{topic_pattern}'")
        
        return success
    
    def unsubscribe(self, client_id: str, topic_pattern: str) -> bool:
        """
        Unsubscribe from a topic pattern.
        
        Args:
            client_id: Client identifier
            topic_pattern: Topic pattern to unsubscribe from
            
        Returns:
            True if unsubscription was successful, False otherwise
        """
        success = self.topic_manager.remove_subscription(client_id, topic_pattern)
        
        if success:
            self._stats["subscriptions_removed"] += 1
            self._logger.info(f"Client {client_id} unsubscribed from '{topic_pattern}'")
        
        return success
    
    def connect_client(self, client_id: str, client_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        Simulate client connection.
        
        Args:
            client_id: Client identifier
            client_info: Optional client information
            
        Returns:
            True if connection was successful, False otherwise
        """
        with self._client_lock:
            if client_id in self._clients:
                self._logger.warning(f"Client {client_id} is already connected")
                return False
            
            self._clients[client_id] = {
                "client_id": client_id,
                "connected_at": time.time(),
                "info": client_info or {},
            }
            
            self._stats["clients_connected"] += 1
            self._logger.info(f"Client {client_id} connected")
            return True
    
    def disconnect_client(self, client_id: str) -> bool:
        """
        Simulate client disconnection.
        
        Args:
            client_id: Client identifier
            
        Returns:
            True if disconnection was successful, False otherwise
        """
        with self._client_lock:
            if client_id not in self._clients:
                self._logger.warning(f"Client {client_id} is not connected")
                return False
            
            # Remove all subscriptions for this client
            removed_subs = self.topic_manager.remove_all_subscriptions(client_id)
            
            # Remove client
            del self._clients[client_id]
            
            self._stats["clients_disconnected"] += 1
            self._stats["subscriptions_removed"] += removed_subs
            
            self._logger.info(
                f"Client {client_id} disconnected "
                f"({removed_subs} subscriptions removed)"
            )
            return True
    
    async def _disconnect_all_clients(self) -> None:
        """Disconnect all clients."""
        with self._client_lock:
            client_ids = list(self._clients.keys())
        
        for client_id in client_ids:
            self.disconnect_client(client_id)
    
    async def _cleanup_loop(self) -> None:
        """Periodic cleanup task."""
        while self._running:
            try:
                # Clean up expired messages
                expired_count = self.message_handler.cleanup_expired_messages()
                if expired_count > 0:
                    self._logger.debug(f"Cleaned up {expired_count} expired messages")
                
                # Wait for next cleanup cycle
                await asyncio.sleep(self._cleanup_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(1)
    
    # Testing utilities
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get broker statistics."""
        stats = self._stats.copy()
        stats.update({
            "running": self._running,
            "uptime_seconds": time.time() - self._stats["start_time"] if self._stats["start_time"] else 0,
            "connected_clients": len(self._clients),
            "active_subscriptions": self.topic_manager.get_subscription_count(),
            "stored_messages": self.message_handler.get_message_count(),
        })
        stats.update(self.message_handler.get_statistics())
        return stats
    
    def get_captured_messages(self) -> List[BrokerMessage]:
        """Get all captured messages for testing."""
        return self.message_handler.get_captured_messages()
    
    def clear_captured_messages(self) -> None:
        """Clear captured messages."""
        self.message_handler.clear_captured_messages()
    
    def add_message_listener(self, listener: Callable[[BrokerMessage], None]) -> None:
        """Add a message listener for testing."""
        self.message_handler.add_message_listener(listener)
    
    def remove_message_listener(self, listener: Callable[[BrokerMessage], None]) -> None:
        """Remove a message listener."""
        self.message_handler.remove_message_listener(listener)
    
    def find_messages_by_topic(self, topic: str, limit: Optional[int] = None) -> List[BrokerMessage]:
        """Find messages by topic."""
        return self.message_handler.get_messages_by_topic(topic, limit)
    
    def find_messages_by_payload(self, payload_filter: Callable[[Any], bool]) -> List[BrokerMessage]:
        """Find messages by payload content."""
        return self.message_handler.find_messages_by_payload(payload_filter)
    
    def get_client_subscriptions(self, client_id: str) -> List[str]:
        """Get all topic patterns for a client."""
        return self.topic_manager.get_subscription_topics(client_id)
    
    def is_running(self) -> bool:
        """Check if the broker is running."""
        return self._running
    
    @property
    def broker_url(self) -> str:
        """Get the broker URL."""
        return self.config.broker_url
    
    @property
    def sac_config(self) -> Dict[str, Any]:
        """Get configuration in SAC format."""
        return self.config.get_sac_broker_config()
