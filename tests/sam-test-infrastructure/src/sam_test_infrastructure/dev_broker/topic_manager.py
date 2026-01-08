"""
Topic management for the development Solace broker simulator.
Handles topic subscriptions, wildcard matching, and message routing.
"""

import re
import threading
from typing import Dict, List, Set, Callable, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import logging


@dataclass
class Subscription:
    """Represents a topic subscription."""
    topic_pattern: str
    qos: int
    callback: Callable[[str, Any], None]
    subscriber_id: str
    
    def matches_topic(self, topic: str) -> bool:
        """Check if this subscription matches the given topic."""
        return topic_matches_subscription(topic, self.topic_pattern)


def topic_matches_subscription(topic: str, subscription: str) -> bool:
    """
    Check if a topic matches a subscription pattern.
    Supports Solace-style wildcards:
    - * matches one level
    - > matches one or more levels at the end
    """
    if topic == subscription:
        return True
    
    # Handle Solace-style wildcards manually
    if ">" in subscription:
        # > wildcard matches everything to the end
        prefix = subscription.replace(">", "")
        return topic.startswith(prefix)
    elif "*" in subscription:
        # * wildcard matches one level
        # Convert to regex pattern
        pattern = re.escape(subscription)
        pattern = pattern.replace(r'\*', r'[^/]+')  # * matches one level (no slashes)
        pattern = f'^{pattern}$'
        try:
            return bool(re.match(pattern, topic))
        except re.error:
            # If regex compilation fails, fall back to exact match
            return topic == subscription
    else:
        # No wildcards, exact match
        return topic == subscription


class TopicManager:
    """Manages topic subscriptions and message routing for the dev broker."""
    
    def __init__(self, max_subscriptions: int = 100):
        self.max_subscriptions = max_subscriptions
        self._subscriptions: Dict[str, Subscription] = {}
        self._topic_index: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()
        self._logger = logging.getLogger(f"{__name__}.TopicManager")
        
    def add_subscription(
        self, 
        subscriber_id: str, 
        topic_pattern: str, 
        callback: Callable[[str, Any], None],
        qos: int = 1
    ) -> bool:
        """
        Add a topic subscription.
        
        Args:
            subscriber_id: Unique identifier for the subscriber
            topic_pattern: Topic pattern with optional wildcards
            callback: Function to call when matching messages arrive
            qos: Quality of service level
            
        Returns:
            True if subscription was added successfully, False otherwise
        """
        with self._lock:
            if len(self._subscriptions) >= self.max_subscriptions:
                self._logger.warning(
                    f"Maximum subscriptions ({self.max_subscriptions}) reached"
                )
                return False
            
            sub_key = f"{subscriber_id}:{topic_pattern}"
            
            if sub_key in self._subscriptions:
                self._logger.debug(f"Subscription already exists: {sub_key}")
                return True
            
            subscription = Subscription(
                topic_pattern=topic_pattern,
                qos=qos,
                callback=callback,
                subscriber_id=subscriber_id
            )
            
            self._subscriptions[sub_key] = subscription
            self._topic_index[topic_pattern].add(sub_key)
            
            self._logger.info(
                f"Added subscription: {subscriber_id} -> {topic_pattern} (QoS: {qos})"
            )
            return True
    
    def remove_subscription(self, subscriber_id: str, topic_pattern: str) -> bool:
        """
        Remove a topic subscription.
        
        Args:
            subscriber_id: Subscriber identifier
            topic_pattern: Topic pattern to unsubscribe from
            
        Returns:
            True if subscription was removed, False if not found
        """
        with self._lock:
            sub_key = f"{subscriber_id}:{topic_pattern}"
            
            if sub_key not in self._subscriptions:
                self._logger.debug(f"Subscription not found: {sub_key}")
                return False
            
            del self._subscriptions[sub_key]
            self._topic_index[topic_pattern].discard(sub_key)
            
            # Clean up empty topic index entries
            if not self._topic_index[topic_pattern]:
                del self._topic_index[topic_pattern]
            
            self._logger.info(f"Removed subscription: {sub_key}")
            return True
    
    def remove_all_subscriptions(self, subscriber_id: str) -> int:
        """
        Remove all subscriptions for a subscriber.
        
        Args:
            subscriber_id: Subscriber identifier
            
        Returns:
            Number of subscriptions removed
        """
        with self._lock:
            removed_count = 0
            keys_to_remove = []
            
            for sub_key, subscription in self._subscriptions.items():
                if subscription.subscriber_id == subscriber_id:
                    keys_to_remove.append(sub_key)
            
            for sub_key in keys_to_remove:
                subscription = self._subscriptions[sub_key]
                del self._subscriptions[sub_key]
                self._topic_index[subscription.topic_pattern].discard(sub_key)
                
                # Clean up empty topic index entries
                if not self._topic_index[subscription.topic_pattern]:
                    del self._topic_index[subscription.topic_pattern]
                
                removed_count += 1
            
            if removed_count > 0:
                self._logger.info(
                    f"Removed {removed_count} subscriptions for {subscriber_id}"
                )
            
            return removed_count
    
    def get_matching_subscriptions(self, topic: str) -> List[Subscription]:
        """
        Get all subscriptions that match the given topic.
        
        Args:
            topic: Topic to match against subscriptions
            
        Returns:
            List of matching subscriptions
        """
        with self._lock:
            matching_subscriptions = []
            
            for subscription in self._subscriptions.values():
                if subscription.matches_topic(topic):
                    matching_subscriptions.append(subscription)
            
            return matching_subscriptions
    
    def route_message(self, topic: str, message: Any) -> int:
        """
        Route a message to all matching subscriptions.
        
        Args:
            topic: Message topic
            message: Message payload
            
        Returns:
            Number of subscriptions the message was delivered to
        """
        matching_subscriptions = self.get_matching_subscriptions(topic)
        
        delivery_count = 0
        for subscription in matching_subscriptions:
            try:
                subscription.callback(topic, message)
                delivery_count += 1
                self._logger.debug(
                    f"Delivered message to {subscription.subscriber_id} "
                    f"(pattern: {subscription.topic_pattern})"
                )
            except Exception as e:
                self._logger.error(
                    f"Error delivering message to {subscription.subscriber_id}: {e}"
                )
        
        if delivery_count > 0:
            self._logger.debug(
                f"Routed message on topic '{topic}' to {delivery_count} subscribers"
            )
        
        return delivery_count
    
    def get_subscription_count(self, subscriber_id: Optional[str] = None) -> int:
        """
        Get the number of subscriptions.
        
        Args:
            subscriber_id: If provided, count only subscriptions for this subscriber
            
        Returns:
            Number of subscriptions
        """
        with self._lock:
            if subscriber_id is None:
                return len(self._subscriptions)
            
            return sum(
                1 for sub in self._subscriptions.values()
                if sub.subscriber_id == subscriber_id
            )
    
    def get_subscription_topics(self, subscriber_id: str) -> List[str]:
        """
        Get all topic patterns for a subscriber.
        
        Args:
            subscriber_id: Subscriber identifier
            
        Returns:
            List of topic patterns
        """
        with self._lock:
            return [
                sub.topic_pattern for sub in self._subscriptions.values()
                if sub.subscriber_id == subscriber_id
            ]
    
    def clear_all_subscriptions(self) -> None:
        """Clear all subscriptions."""
        with self._lock:
            count = len(self._subscriptions)
            self._subscriptions.clear()
            self._topic_index.clear()
            
            if count > 0:
                self._logger.info(f"Cleared all {count} subscriptions")
