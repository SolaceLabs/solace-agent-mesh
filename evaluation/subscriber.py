"""
Refactored message subscriber with improved structure and readability.
This module handles Solace message subscription and processing for evaluation.
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from solace.messaging.messaging_service import MessagingService
from solace.messaging.resources.topic_subscription import TopicSubscription

from .shared import (
    ALLOWED_TOPIC_INFIXES,
    BLOCKED_TOPIC_INFIXES,
    MESSAGE_TIMEOUT,
    BrokerConfig,
    BrokerConnectionError,
    ConfigurationError,
    ConnectionState,
    MessageProcessingError,
)

log = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


@dataclass
class SubscriptionConfig:
    """Subscription configuration and topic filters."""

    namespace: str
    allowed_topic_infixes: list[str] = field(
        default_factory=lambda: ALLOWED_TOPIC_INFIXES
    )
    blocked_topic_infixes: list[str] = field(
        default_factory=lambda: BLOCKED_TOPIC_INFIXES
    )
    message_timeout: int = MESSAGE_TIMEOUT
    filter_non_final_status: bool = True
    remove_config_keys: bool = False

    def __post_init__(self):
        """Validate subscription configuration."""
        if not self.namespace or not self.namespace.strip():
            raise ConfigurationError("Namespace cannot be empty")

        if not self.allowed_topic_infixes:
            raise ConfigurationError("At least one topic infix must be allowed")

        if self.message_timeout <= 0:
            raise ConfigurationError("Message timeout must be positive")

    @property
    def topic_pattern(self) -> str:
        """Get the topic subscription pattern."""
        return f"{self.namespace}/a2a/v1/>"

    def is_topic_allowed(self, topic: str) -> bool:
        """Check if a topic is allowed based on configured infixes."""
        # return any(infix in topic for infix in self.allowed_topic_infixes)
        return not any(infix in topic for infix in self.blocked_topic_infixes)


@dataclass
class ProcessedMessage:
    """Structured representation of a processed message."""

    topic: str
    payload: any
    timestamp: float = field(default_factory=time.time)
    message_type: str | None = None

    def to_dict(self) -> dict[str, any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "topic": self.topic,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "message_type": self.message_type,
        }


@dataclass
class TaskCompletionEvent:
    """Represents a task completion event."""

    task_id: str
    topic: str
    timestamp: float = field(default_factory=time.time)


class MessageSanitizer:
    """Handles message sanitization and cleaning."""

    @staticmethod
    def remove_key_recursive(obj: any, key_to_remove: str) -> None:
        """
        Recursively remove a key from nested dictionaries and lists.

        Args:
            obj: The object to process (dict, list, or other)
            key_to_remove: The key to remove from dictionaries
        """
        try:
            if isinstance(obj, dict):
                # Create a list of keys to avoid modifying dict during iteration
                keys_to_process = list(obj.keys())
                for key in keys_to_process:
                    if key == key_to_remove:
                        del obj[key]
                    else:
                        MessageSanitizer.remove_key_recursive(obj[key], key_to_remove)
            elif isinstance(obj, list):
                for item in obj:
                    MessageSanitizer.remove_key_recursive(item, key_to_remove)
        except Exception as e:
            log.warning(f"Error during key removal: {e}")

    @staticmethod
    def sanitize_message(payload: any, remove_config: bool = True) -> any:
        """
        Sanitize message payload by removing unwanted keys.

        Args:
            payload: The payload to sanitize
            remove_config: Whether to remove 'config' keys

        Returns:
            Sanitized payload
        """
        if remove_config and isinstance(payload, (dict, list)):
            # Work on a copy to avoid modifying the original
            import copy

            sanitized = copy.deepcopy(payload)
            MessageSanitizer.remove_key_recursive(sanitized, "config")
            return sanitized
        return payload


class MessageProcessor:
    """Processes and filters incoming messages."""

    def __init__(self, config: SubscriptionConfig):
        self.config = config
        self.sanitizer = MessageSanitizer()
        self.processed_count = 0
        self.error_count = 0

    def process_message(self, inbound_message) -> ProcessedMessage | None:
        """
        Process an inbound message and return a ProcessedMessage if valid.

        Args:
            inbound_message: The inbound Solace message

        Returns:
            ProcessedMessage if the message should be kept, None otherwise
        """
        try:
            topic = inbound_message.get_destination_name()

            # Check if topic is allowed
            if not self.config.is_topic_allowed(topic):
                return None

            # Extract and parse payload
            payload = self._extract_payload(inbound_message)
            if payload is None:
                return None

            # Filter status messages if configured
            if self._should_filter_status_message(topic, payload):
                return None

            # Sanitize payload
            if self.config.remove_config_keys:
                payload = self.sanitizer.sanitize_message(payload)

            # Determine message type
            message_type = self._determine_message_type(topic)

            self.processed_count += 1

            return ProcessedMessage(
                topic=topic, payload=payload, message_type=message_type
            )

        except Exception as e:
            self.error_count += 1
            log.warning(f"Error processing message: {e}")
            return None

    def _extract_payload(self, inbound_message):
        """Extract and parse payload from inbound message."""
        try:
            payload_bytes = inbound_message.get_payload_as_bytes()
            if not payload_bytes:
                return None

            payload_str = payload_bytes.decode("utf-8", errors="ignore")

            # Try to parse as JSON
            try:
                return json.loads(payload_str)
            except json.JSONDecodeError:
                # Return as string if not valid JSON
                return payload_str

        except Exception as e:
            log.warning(f"Error extracting payload: {e}")
            return None

    def _should_filter_status_message(self, topic: str, payload: any) -> bool:
        """Check if a status message should be filtered out."""
        if not self.config.filter_non_final_status:
            return False

        try:
            # Filter only for llm_invocation
            if self._find_part_type(payload, "llm_invocation"):
                return True

            # Filter only for llm_response
            if self._find_part_type(payload, "llm_response"):
                return True

            # Filter out agent progress update messages
            if self._find_part_type(payload, "agent_progress_update"):
                return True
        except Exception:
            pass

        return False

    def _find_part_type(self, data: any, type_to_find: str) -> bool:
        """Recursively search for a part with a specific type."""
        if isinstance(data, dict):
            if data.get("type") == type_to_find:
                return True
            for _key, value in data.items():
                if self._find_part_type(value, type_to_find):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._find_part_type(item, type_to_find):
                    return True
        return False

    def _determine_message_type(self, topic: str) -> str:
        """Determine the type of message based on topic."""
        if "/agent/request/" in topic:
            return "agent_request"
        elif "/gateway/status/" in topic:
            return "gateway_status"
        elif "/gateway/response/" in topic:
            return "gateway_response"
        else:
            return "unknown"

    def get_stats(self) -> dict[str, int]:
        """Get processing statistics."""
        return {
            "processed_count": self.processed_count,
            "error_count": self.error_count,
        }


class TaskTracker:
    """Tracks task completion and manages active tasks."""

    def __init__(
        self, active_tasks: set[str], wave_complete_event: threading.Event | None
    ):
        self.active_tasks = active_tasks
        self.wave_complete_event = wave_complete_event
        self.completed_tasks: list[TaskCompletionEvent] = []
        self._lock = threading.Lock()

    def handle_task_completion(self, topic: str) -> TaskCompletionEvent | None:
        """
        Handle task completion based on topic.

        Args:
            topic: The message topic

        Returns:
            TaskCompletionEvent if a task was completed, None otherwise
        """
        if "response" not in topic:
            return None

        try:
            task_id = self._extract_task_id(topic)
            if not task_id:
                return None

            with self._lock:
                if task_id in self.active_tasks:
                    log.info(f"Task {task_id} completed")
                    self.active_tasks.remove(task_id)

                    completion_event = TaskCompletionEvent(task_id=task_id, topic=topic)
                    self.completed_tasks.append(completion_event)

                    # Check if all tasks are complete
                    if not self.active_tasks and self.wave_complete_event:
                        log.info("All tasks completed, setting wave complete event")
                        self.wave_complete_event.set()

                    return completion_event

        except Exception as e:
            log.error(f"Error handling task completion: {e}")

        return None

    def _extract_task_id(self, topic: str) -> str | None:
        """Extract task ID from topic."""
        try:
            return topic.split("/")[-1]
        except (IndexError, AttributeError):
            return None

    def get_active_task_count(self) -> int:
        """Get the number of active tasks."""
        with self._lock:
            return len(self.active_tasks)

    def get_completed_task_count(self) -> int:
        """Get the number of completed tasks."""
        with self._lock:
            return len(self.completed_tasks)


class MessageStorage:
    """Handles message storage and file operations."""

    def __init__(self, results_path: str | Path):
        self.results_path = Path(results_path)
        self.messages: list[ProcessedMessage] = []
        self._lock = threading.Lock()

    def add_message(self, message: ProcessedMessage) -> None:
        """Add a message to storage."""
        with self._lock:
            self.messages.append(message)

    def get_message_count(self) -> int:
        """Get the number of stored messages."""
        with self._lock:
            return len(self.messages)

    def save_messages(self, filename: str = "full_messages.json") -> str:
        """
        Save all messages to a JSON file.

        Args:
            filename: The filename to save to

        Returns:
            The full path to the saved file
        """
        output_file = self.results_path / filename

        try:
            # Ensure directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with self._lock:
                # Convert messages to dictionaries for JSON serialization
                message_dicts = [msg.to_dict() for msg in self.messages]

            with output_file.open("w") as f:
                json.dump(message_dicts, f, indent=4)

            log.info(f"Saved {len(message_dicts)} messages to {output_file}")
            return str(output_file)

        except Exception as e:
            log.error(f"Error saving messages: {e}")
            raise MessageProcessingError(f"Failed to save messages: {e}") from e

    def clear_messages(self) -> None:
        """Clear all stored messages."""
        with self._lock:
            self.messages.clear()


class BrokerConnectionService:
    """Handles Solace broker connection and lifecycle."""

    def __init__(self, config: BrokerConfig):
        self.config = config
        self.messaging_service: MessagingService | None = None
        self.connection_state = ConnectionState.DISCONNECTED
        self._connection_lock = threading.Lock()

    def connect(self) -> None:
        """Connect to the Solace broker."""
        with self._connection_lock:
            if self.connection_state == ConnectionState.CONNECTED:
                log.warning("Already connected to broker")
                return

            self.connection_state = ConnectionState.CONNECTING

            try:
                log.info("Connecting to Solace PubSub+ Broker...")

                broker_props = self.config.to_solace_properties()
                self.messaging_service = (
                    MessagingService.builder().from_properties(broker_props).build()
                )
                self.messaging_service.connect()

                self.connection_state = ConnectionState.CONNECTED
                log.info("Successfully connected to broker")

            except Exception as e:
                self.connection_state = ConnectionState.ERROR
                log.error(f"Failed to connect to broker: {e}")
                raise BrokerConnectionError(f"Connection failed: {e}") from e

    def disconnect(self) -> None:
        """Disconnect from the Solace broker."""
        with self._connection_lock:
            if self.connection_state == ConnectionState.DISCONNECTED:
                log.warning("Already disconnected from broker")
                return

            self.connection_state = ConnectionState.DISCONNECTING

            try:
                if self.messaging_service:
                    log.info("Disconnecting from broker...")
                    self.messaging_service.disconnect()
                    self.messaging_service = None

                self.connection_state = ConnectionState.DISCONNECTED
                log.info("Successfully disconnected from broker")

            except Exception as e:
                self.connection_state = ConnectionState.ERROR
                log.error(f"Error during disconnect: {e}")
                raise BrokerConnectionError(f"Disconnect failed: {e}") from e

    def get_messaging_service(self) -> MessagingService | None:
        """Get the messaging service instance."""
        return self.messaging_service

    def is_connected(self) -> bool:
        """Check if currently connected to broker."""
        return self.connection_state == ConnectionState.CONNECTED

    def get_connection_state(self) -> ConnectionState:
        """Get the current connection state."""
        return self.connection_state


class SubscriptionManager:
    """Manages topic subscriptions and message receiving."""

    def __init__(
        self, connection_service: BrokerConnectionService, config: SubscriptionConfig
    ):
        self.connection_service = connection_service
        self.config = config
        self.message_receiver = None
        self.subscription_active = False
        self._receiver_lock = threading.Lock()

    def start_subscription(
        self, subscription_ready_event: threading.Event | None = None
    ) -> None:
        """Start message subscription."""
        with self._receiver_lock:
            if self.subscription_active:
                log.warning("Subscription already active")
                return

            if not self.connection_service.is_connected():
                raise BrokerConnectionError(
                    "Must be connected to broker before starting subscription"
                )

            try:
                messaging_service = self.connection_service.get_messaging_service()
                if not messaging_service:
                    raise BrokerConnectionError("No messaging service available")

                # Create and start message receiver
                self.message_receiver = (
                    messaging_service.create_direct_message_receiver_builder().build()
                )
                self.message_receiver.start()

                # Add subscription
                subscription = TopicSubscription.of(self.config.topic_pattern)
                self.message_receiver.add_subscription(subscription)

                self.subscription_active = True
                log.info(f"Started subscription to: {self.config.topic_pattern}")

                # Signal that subscription is ready
                if subscription_ready_event:
                    subscription_ready_event.set()

            except Exception as e:
                log.error(f"Failed to start subscription: {e}")
                raise BrokerConnectionError(f"Subscription failed: {e}") from e

    def receive_message(self, timeout: int | None = None):
        """
        Receive a message from the subscription.

        Args:
            timeout: Timeout in milliseconds, uses config default if None

        Returns:
            Received message or None if timeout
        """
        if not self.subscription_active or not self.message_receiver:
            return None

        timeout_ms = timeout or self.config.message_timeout

        try:
            return self.message_receiver.receive_message(timeout=timeout_ms)
        except Exception as e:
            log.warning(f"Error receiving message: {e}")
            return None

    def stop_subscription(self) -> None:
        """Stop message subscription."""
        with self._receiver_lock:
            if not self.subscription_active:
                return

            try:
                if self.message_receiver:
                    log.info("Stopping message receiver...")
                    self.message_receiver.terminate()
                    self.message_receiver = None

                self.subscription_active = False
                log.info("Subscription stopped")

            except Exception as e:
                log.error(f"Error stopping subscription: {e}")

    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.subscription_active


class Subscriber(threading.Thread):
    """
    Main message subscriber class that orchestrates all components.
    This is the refactored version of the original Subscriber class,
    maintaining the same interface while providing better structure.
    """

    def __init__(
        self,
        broker_config: BrokerConfig,
        namespace: str,
        active_tasks: set[str],
        wave_complete_event: threading.Event | None,
        subscription_ready_event: threading.Event | None,
        results_path: str,
    ):
        """
        Initialize the message subscriber.
        Args:
            broker_config: The broker configuration object
            namespace: The namespace for topic subscription
            active_tasks: Set of active task IDs to track
            wave_complete_event: Event to set when all tasks complete
            subscription_ready_event: Event to set when subscription is ready
            results_path: Path to save results
        """
        super().__init__(name="Subscriber")

        # Initialize configuration
        self.broker_config = broker_config
        self.subscription_config = SubscriptionConfig(namespace=namespace)

        # Initialize services
        self.connection_service = BrokerConnectionService(self.broker_config)
        self.subscription_manager = SubscriptionManager(
            self.connection_service, self.subscription_config
        )
        self.message_processor = MessageProcessor(self.subscription_config)
        self.task_tracker = TaskTracker(active_tasks, wave_complete_event)
        self.message_storage = MessageStorage(results_path)

        # Thread control
        self._running = False
        self._subscription_ready_event = subscription_ready_event

        # Statistics
        self.start_time = time.time()
        self.messages_received = 0
        self.messages_processed = 0

    def run(self) -> None:
        """Main thread execution method."""
        try:
            self._running = True
            log.info("Starting message subscriber...")

            # Connect to broker
            self.connection_service.connect()

            # Start subscription
            self.subscription_manager.start_subscription(self._subscription_ready_event)

            # Main message processing loop
            self._message_processing_loop()

        except Exception as e:
            log.error(f"Error in subscriber thread: {e}")
        finally:
            self._cleanup()

    def _message_processing_loop(self) -> None:
        """Main message processing loop."""
        log.info("Starting message processing loop...")

        while self._running:
            try:
                # Receive message with timeout
                inbound_message = self.subscription_manager.receive_message()

                if inbound_message:
                    self.messages_received += 1
                    self._handle_inbound_message(inbound_message)

            except Exception as e:
                if self._running:
                    log.error(f"Error in message processing loop: {e}")
                    # Continue processing other messages
                    continue

    def _handle_inbound_message(self, inbound_message) -> None:
        """Handle a single inbound message."""
        try:
            # Process the message
            processed_message = self.message_processor.process_message(inbound_message)

            if processed_message:
                self.messages_processed += 1

                # Store the message
                self.message_storage.add_message(processed_message)

                # Handle task completion if applicable
                self.task_tracker.handle_task_completion(processed_message.topic)

        except Exception as e:
            log.warning(f"Error handling message: {e}")

    def stop(self) -> None:
        """Stop the subscriber and clean up resources."""
        log.info("Stopping message subscriber...")
        self._running = False

    def _cleanup(self) -> None:
        """Clean up all resources."""
        try:
            # Stop subscription
            self.subscription_manager.stop_subscription()

            # Disconnect from broker
            self.connection_service.disconnect()

            # Save messages
            self.message_storage.save_messages()

            # Log final statistics
            self._log_final_statistics()

        except Exception as e:
            log.error(f"Error during cleanup: {e}")

    def _log_final_statistics(self) -> None:
        """Log final processing statistics."""
        runtime = time.time() - self.start_time
        processor_stats = self.message_processor.get_stats()

        log.info("=== SUBSCRIBER STATISTICS ===")
        log.info(f"Runtime: {runtime:.2f} seconds")
        log.info(f"Messages received: {self.messages_received}")
        log.info(f"Messages processed: {self.messages_processed}")
        log.info(f"Messages stored: {self.message_storage.get_message_count()}")
        log.info(f"Processing errors: {processor_stats['error_count']}")
        log.info(
            f"Active tasks remaining: {self.task_tracker.get_active_task_count()}"
        )
        log.info(f"Tasks completed: {self.task_tracker.get_completed_task_count()}")
        log.info("=============================")

    # Backward compatibility properties
    @property
    def active_tasks(self) -> set[str]:
        """Get active tasks set for backward compatibility."""
        return self.task_tracker.active_tasks

    @property
    def messages(self) -> list[dict[str, any]]:
        """Get messages list for backward compatibility."""
        return [msg.to_dict() for msg in self.message_storage.messages]




def main():
    """Main entry point for testing the subscriber."""
    import signal
    import sys

    # Set up signal handling for graceful shutdown
    def signal_handler(signum, frame):
        log.info("\nShutting down subscriber...")
        if "subscriber" in locals():
            subscriber.stop()
            subscriber.join()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create test subscriber
    active_tasks = set()
    subscription_ready = threading.Event()

    try:
        broker_config = BrokerConfig(
            host=os.environ.get("SOLACE_BROKER_URL", ""),
            vpn_name=os.environ.get("SOLACE_BROKER_VPN", ""),
            username=os.environ.get("SOLACE_BROKER_USERNAME", ""),
            password=os.environ.get("SOLACE_BROKER_PASSWORD", ""),
        )
        subscriber = Subscriber(
            broker_config=broker_config,
            namespace="test",
            active_tasks=active_tasks,
            subscription_ready_event=subscription_ready,
            results_path=".",
        )

        subscriber.start()

        # Wait for subscription to be ready
        subscription_ready.wait(timeout=30)
        log.info("Subscriber is ready and running...")

        # Keep running until interrupted
        subscriber.join()

    except Exception as e:
        log.error(f"Error running subscriber: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
