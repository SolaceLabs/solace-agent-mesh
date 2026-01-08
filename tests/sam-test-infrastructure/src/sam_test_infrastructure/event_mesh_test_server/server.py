"""
Event Mesh Test Server for comprehensive testing of the Event Mesh Gateway.
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable, Union
import logging

from ..dev_broker import DevBroker, BrokerConfig, BrokerMessage


class EventMeshTestServer:
    """
    Test server that combines a dev broker with testing utilities
    for comprehensive Event Mesh Gateway testing.
    """
    
    def __init__(self, broker_config: Optional[BrokerConfig] = None):
        self.broker_config = broker_config or BrokerConfig()
        self.dev_broker = DevBroker(self.broker_config)
        self._logger = logging.getLogger(f"{__name__}.EventMeshTestServer")
        
        # Test state
        self._test_scenarios: Dict[str, Dict[str, Any]] = {}
        self._expected_messages: List[Dict[str, Any]] = []
        self._received_messages: List[BrokerMessage] = []
        self._message_expectations: List[Callable[[BrokerMessage], bool]] = []
        
        # Event tracking
        self._event_listeners: List[Callable[[str, Any], None]] = []
        
        # Setup message listener
        self.dev_broker.add_message_listener(self._on_message_received)
        
        self._logger.info(f"EventMeshTestServer initialized on {self.broker_url}")
    
    async def start(self) -> None:
        """Start the test server."""
        await self.dev_broker.start()
        self._logger.info("EventMeshTestServer started")
    
    async def stop(self) -> None:
        """Stop the test server."""
        await self.dev_broker.stop()
        self._logger.info("EventMeshTestServer stopped")
    
    def _on_message_received(self, message: BrokerMessage) -> None:
        """Handle received messages for testing."""
        self._received_messages.append(message)
        
        # Check against expectations
        for expectation in self._message_expectations:
            try:
                if expectation(message):
                    self._logger.debug(f"Message {message.id} matched expectation")
            except Exception as e:
                self._logger.error(f"Error checking message expectation: {e}")
        
        # Notify event listeners
        for listener in self._event_listeners:
            try:
                listener("message_received", message)
            except Exception as e:
                self._logger.error(f"Error in event listener: {e}")
    
    # Message publishing methods
    
    def publish_test_message(
        self,
        topic: str,
        payload: Any,
        user_properties: Optional[Dict[str, Any]] = None,
        qos: int = 1
    ) -> BrokerMessage:
        """
        Publish a test message.
        
        Args:
            topic: Message topic
            payload: Message payload
            user_properties: Optional user properties
            qos: Quality of service level
            
        Returns:
            The published message
        """
        return self.dev_broker.publish_message(
            topic=topic,
            payload=payload,
            user_properties=user_properties,
            qos=qos
        )
    
    def publish_json_message(
        self,
        topic: str,
        json_data: Dict[str, Any],
        user_properties: Optional[Dict[str, Any]] = None
    ) -> BrokerMessage:
        """Publish a JSON message."""
        return self.publish_test_message(
            topic=topic,
            payload=json_data,
            user_properties=user_properties
        )
    
    def publish_text_message(
        self,
        topic: str,
        text: str,
        user_properties: Optional[Dict[str, Any]] = None
    ) -> BrokerMessage:
        """Publish a text message."""
        return self.publish_test_message(
            topic=topic,
            payload=text,
            user_properties=user_properties
        )
    
    # Subscription methods
    
    def subscribe_to_topic(
        self,
        client_id: str,
        topic_pattern: str,
        callback: Optional[Callable[[str, BrokerMessage], None]] = None,
        qos: int = 1
    ) -> bool:
        """
        Subscribe to a topic pattern.
        
        Args:
            client_id: Client identifier
            topic_pattern: Topic pattern with optional wildcards
            callback: Optional callback function
            qos: Quality of service level
            
        Returns:
            True if subscription was successful
        """
        # Ensure client is connected
        self.dev_broker.connect_client(client_id)
        
        if callback is None:
            # Default callback that just logs
            def default_callback(topic: str, message: BrokerMessage) -> None:
                self._logger.debug(f"Received message on {topic}: {message.id}")
            callback = default_callback
        
        return self.dev_broker.subscribe(
            client_id=client_id,
            topic_pattern=topic_pattern,
            callback=callback,
            qos=qos
        )
    
    # Test scenario management
    
    def load_test_scenario(self, scenario_name: str, scenario_config: Dict[str, Any]) -> None:
        """
        Load a test scenario configuration.
        
        Args:
            scenario_name: Name of the scenario
            scenario_config: Scenario configuration
        """
        self._test_scenarios[scenario_name] = scenario_config
        self._logger.info(f"Loaded test scenario: {scenario_name}")
    
    def get_test_scenario(self, scenario_name: str) -> Optional[Dict[str, Any]]:
        """Get a test scenario configuration."""
        return self._test_scenarios.get(scenario_name)
    
    def execute_test_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """
        Execute a test scenario.
        
        Args:
            scenario_name: Name of the scenario to execute
            
        Returns:
            Execution results
        """
        scenario = self.get_test_scenario(scenario_name)
        if not scenario:
            raise ValueError(f"Test scenario '{scenario_name}' not found")
        
        self._logger.info(f"Executing test scenario: {scenario_name}")
        
        results = {
            "scenario_name": scenario_name,
            "start_time": time.time(),
            "steps_executed": 0,
            "steps_failed": 0,
            "messages_published": 0,
            "messages_received": 0,
            "errors": [],
        }
        
        try:
            steps = scenario.get("steps", [])
            for i, step in enumerate(steps):
                try:
                    self._execute_scenario_step(step, results)
                    results["steps_executed"] += 1
                except Exception as e:
                    results["steps_failed"] += 1
                    results["errors"].append(f"Step {i}: {str(e)}")
                    self._logger.error(f"Error in scenario step {i}: {e}")
        
        except Exception as e:
            results["errors"].append(f"Scenario execution error: {str(e)}")
            self._logger.error(f"Error executing scenario {scenario_name}: {e}")
        
        results["end_time"] = time.time()
        results["duration"] = results["end_time"] - results["start_time"]
        
        self._logger.info(
            f"Scenario {scenario_name} completed: "
            f"{results['steps_executed']} steps executed, "
            f"{results['steps_failed']} failed"
        )
        
        return results
    
    def _execute_scenario_step(self, step: Dict[str, Any], results: Dict[str, Any]) -> None:
        """Execute a single scenario step."""
        step_type = step.get("type")
        
        if step_type == "publish_message":
            topic = step["topic"]
            payload = step["payload"]
            user_properties = step.get("user_properties")
            
            self.publish_test_message(
                topic=topic,
                payload=payload,
                user_properties=user_properties
            )
            results["messages_published"] += 1
            
        elif step_type == "subscribe":
            client_id = step["client_id"]
            topic_pattern = step["topic_pattern"]
            
            self.subscribe_to_topic(
                client_id=client_id,
                topic_pattern=topic_pattern
            )
            
        elif step_type == "wait":
            duration = step.get("duration", 1.0)
            time.sleep(duration)
            
        elif step_type == "expect_message":
            # Add message expectation
            topic_pattern = step.get("topic_pattern")
            payload_contains = step.get("payload_contains")
            
            def expectation(message: BrokerMessage) -> bool:
                if topic_pattern and not message.topic.startswith(topic_pattern.replace("*", "")):
                    return False
                if payload_contains and payload_contains not in str(message.payload):
                    return False
                return True
            
            self._message_expectations.append(expectation)
            
        else:
            raise ValueError(f"Unknown step type: {step_type}")
    
    # Message validation and testing utilities
    
    def expect_message_on_topic(
        self,
        topic_pattern: str,
        timeout_seconds: float = 5.0,
        payload_filter: Optional[Callable[[Any], bool]] = None
    ) -> Optional[BrokerMessage]:
        """
        Wait for a message on a specific topic.
        
        Args:
            topic_pattern: Topic pattern to match
            timeout_seconds: Maximum time to wait
            payload_filter: Optional payload filter function
            
        Returns:
            The matching message if found, None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            for message in self._received_messages:
                # Check topic match
                if not self._topic_matches_pattern(message.topic, topic_pattern):
                    continue
                
                # Check payload filter
                if payload_filter and not payload_filter(message.payload):
                    continue
                
                return message
            
            time.sleep(0.1)
        
        return None
    
    def _topic_matches_pattern(self, topic: str, pattern: str) -> bool:
        """Check if a topic matches a pattern."""
        # Simple pattern matching - can be enhanced
        if "*" in pattern:
            pattern_parts = pattern.split("*")
            if len(pattern_parts) == 2:
                prefix, suffix = pattern_parts
                return topic.startswith(prefix) and topic.endswith(suffix)
        elif ">" in pattern:
            prefix = pattern.replace(">", "")
            return topic.startswith(prefix)
        else:
            return topic == pattern
    
    def get_messages_for_topic(self, topic: str) -> List[BrokerMessage]:
        """Get all received messages for a specific topic."""
        return [msg for msg in self._received_messages if msg.topic == topic]
    
    def get_recent_messages(self, limit: int = 10) -> List[BrokerMessage]:
        """Get the most recent received messages."""
        return self._received_messages[-limit:]
    
    def get_captured_messages(self) -> List[BrokerMessage]:
        """Get all captured messages (alias for get_recent_messages with no limit)."""
        return self._received_messages.copy()
    
    def clear_received_messages(self) -> None:
        """Clear the received messages list."""
        self._received_messages.clear()
        self._logger.debug("Cleared received messages")
    
    def add_event_listener(self, listener: Callable[[str, Any], None]) -> None:
        """Add an event listener."""
        self._event_listeners.append(listener)
    
    def remove_event_listener(self, listener: Callable[[str, Any], None]) -> None:
        """Remove an event listener."""
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)
    
    # Properties and utilities
    
    @property
    def broker_url(self) -> str:
        """Get the broker URL."""
        return self.dev_broker.broker_url
    
    @property
    def sac_config(self) -> Dict[str, Any]:
        """Get configuration in SAC format."""
        return self.dev_broker.sac_config
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get server statistics."""
        stats = self.dev_broker.get_statistics()
        stats.update({
            "test_scenarios_loaded": len(self._test_scenarios),
            "received_messages": len(self._received_messages),
            "message_expectations": len(self._message_expectations),
            "event_listeners": len(self._event_listeners),
        })
        return stats
    
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.dev_broker.is_running()
