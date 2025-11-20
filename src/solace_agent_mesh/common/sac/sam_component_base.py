"""
Base Component class for SAM implementations in the Solace AI Connector.
"""

import logging
import abc
import asyncio
import concurrent.futures
import threading
import functools
import time
from typing import Any, Optional

from solace_ai_connector.components.component_base import ComponentBase

from ..exceptions import ComponentInitializationError, MessageSizeExceededError
from ..utils.message_utils import validate_message_size

log = logging.getLogger(__name__)
trace_logger = logging.getLogger("sam_trace")


class SamComponentBase(ComponentBase, abc.ABC):
    """
    Abstract base class for high-level SAM components (Agents, Gateways).

    Provides a standardized framework for:
    - Managing a dedicated asyncio event loop running in a separate thread.
    - Publishing A2A messages with built-in size validation.
    """

    def __init__(self, info: dict[str, Any], **kwargs: Any):
        super().__init__(info, **kwargs)
        log.info("%s Initializing SamComponentBase...", self.log_identifier)

        try:
            self.namespace: str = self.get_config("namespace")
            if not self.namespace:
                raise ValueError("Namespace must be configured in the app_config.")

            # For agents, this is 'max_message_size_bytes'.
            # For gateways, this is 'gateway_max_message_size_bytes'.
            self.max_message_size_bytes: int = self.get_config(
                "max_message_size_bytes"
            ) or self.get_config("gateway_max_message_size_bytes")

            if not self.max_message_size_bytes:
                raise ValueError(
                    "max_message_size_bytes (or gateway_max_message_size_bytes) must be configured."
                )

        except Exception as e:
            log.error(
                "%s Failed to retrieve essential configuration: %s",
                self.log_identifier,
                e,
            )
            raise ValueError(f"Configuration retrieval error: {e}") from e

        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._async_thread: threading.Thread | None = None

        # Timer callback registry
        self._timer_callbacks: dict[str, Any] = {}
        self._timer_callbacks_lock = threading.Lock()

        # Trust Manager integration (enterprise feature) - initialized as part of _late_init
        self.trust_manager: Optional[Any] = None

        log.info("%s Initialized SamComponentBase", self.log_identifier)

    def add_timer(
        self,
        delay_ms: int,
        timer_id: str,
        interval_ms: int = 0,
        callback: Optional[Any] = None,
    ):
        """
        Add a timer with optional callback.

        Args:
            delay_ms: Initial delay in milliseconds
            timer_id: Unique timer identifier
            interval_ms: Repeat interval in milliseconds (0 for one-shot)
            callback: Optional callback function to invoke when timer fires.
                     If provided, callback will be invoked when timer event occurs.
                     Callback receives timer_data dict as argument.
                     Callback should be thread-safe or schedule work appropriately.
        """
        # Register callback if provided
        if callback:
            with self._timer_callbacks_lock:
                if timer_id in self._timer_callbacks:
                    log.warning(
                        "%s Timer ID '%s' already has a registered callback. Overwriting.",
                        self.log_identifier,
                        timer_id,
                    )
                self._timer_callbacks[timer_id] = callback
                log.debug(
                    "%s Registered callback for timer: %s",
                    self.log_identifier,
                    timer_id,
                )

        # Call parent implementation to actually create the timer
        super().add_timer(delay_ms=delay_ms, timer_id=timer_id, interval_ms=interval_ms)

    def cancel_timer(self, timer_id: str):
        """
        Cancel a timer and remove its callback if registered.

        Args:
            timer_id: Timer identifier to cancel
        """
        # Remove callback registration
        with self._timer_callbacks_lock:
            if timer_id in self._timer_callbacks:
                del self._timer_callbacks[timer_id]
                log.debug(
                    "%s Unregistered callback for timer: %s",
                    self.log_identifier,
                    timer_id,
                )

        # Call parent implementation to actually cancel the timer
        super().cancel_timer(timer_id)

    def process_event(self, event):
        """
        Process incoming events by routing to appropriate handlers.

        This base implementation handles MESSAGE and TIMER events:
        - MESSAGE events are routed to _handle_message() abstract method
        - TIMER events are routed to registered callbacks
        - Other events are passed to parent class

        Args:
            event: Event object from SAC framework
        """
        from solace_ai_connector.common.event import Event, EventType
        from solace_ai_connector.common.message import Message as SolaceMessage

        if event.event_type == EventType.MESSAGE:
            message: SolaceMessage = event.data
            topic = message.get_topic()

            if not topic:
                log.warning(
                    "%s Received message without topic. Ignoring.",
                    self.log_identifier,
                )
                try:
                    message.call_negative_acknowledgements()
                except Exception as nack_e:
                    log.error(
                        "%s Failed to NACK message without topic: %s",
                        self.log_identifier,
                        nack_e,
                    )
                return

            try:
                # Delegate to abstract method implemented by subclass
                self._handle_message(message, topic)
            except Exception as e:
                log.error(
                    "%s Error in _handle_message for topic %s: %s",
                    self.log_identifier,
                    topic,
                    e,
                    exc_info=True,
                )
                try:
                    message.call_negative_acknowledgements()
                except Exception as nack_e:
                    log.error(
                        "%s Failed to NACK message after error: %s",
                        self.log_identifier,
                        nack_e,
                    )
                self.handle_error(e, event)

        elif event.event_type == EventType.TIMER:
            # Handle timer events via callback registry
            timer_data = event.data
            timer_id = timer_data.get("timer_id")

            if not timer_id:
                log.warning(
                    "%s Timer event missing timer_id: %s",
                    self.log_identifier,
                    timer_data,
                )
                return

            # Look up registered callback
            with self._timer_callbacks_lock:
                callback = self._timer_callbacks.get(timer_id)

            if callback:
                try:
                    log.debug(
                        "%s Invoking registered callback for timer: %s",
                        self.log_identifier,
                        timer_id,
                    )
                    callback(timer_data)
                except Exception as e:
                    log.error(
                        "%s Error in timer callback for %s: %s",
                        self.log_identifier,
                        timer_id,
                        e,
                        exc_info=True,
                    )
            else:
                log.warning(
                    "%s No callback registered for timer: %s. Timer event ignored.",
                    self.log_identifier,
                    timer_id,
                )
        elif event.event_type == EventType.CACHE_EXPIRY:  
            import asyncio
            import inspect

            cache_data = event.data
            handler = self.handle_cache_expiry_event

            # Check if the handler is async
            if inspect.iscoroutinefunction(handler):
                # Schedule async handler on the event loop
                if self._async_loop and self._async_loop.is_running():
                    async def handle_async():
                        await handler(cache_data)

                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            handle_async(),
                            self._async_loop
                        )

                        def on_done(f):
                            try:
                                f.result()
                            except Exception as e:
                                log.error(
                                    "%s Error in async cache expiry handler: %s",
                                    self.log_identifier,
                                    e,
                                    exc_info=True
                                )
                        future.add_done_callback(on_done)
                    except RuntimeError as e:
                        log.error(
                            "%s Failed to schedule async CACHE_EXPIRY handler (event loop may be stopping): %s",
                            self.log_identifier,
                            e
                        )
                else:
                    log.error(
                        "%s Cannot handle async CACHE_EXPIRY: event loop not available",
                        self.log_identifier
                    )
            else:
                handler(cache_data)
        else:
            # Pass other event types to parent class
            super().process_event(event)

    def _handle_message(self, message, topic: str) -> None:
        """
        Handle an incoming message by routing to async handler.

        This base implementation schedules async processing on the component's
        event loop. Subclasses can override this for custom sync handling,
        or implement _handle_message_async() for async handling.

        Args:
            message: The Solace message (SolaceMessage instance)
            topic: The topic the message was received on
        """
        loop = self.get_async_loop()
        if loop and loop.is_running():
            # Schedule async processing
            coro = self._handle_message_async(message, topic)
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            future.add_done_callback(
                functools.partial(self._handle_async_message_completion, topic=topic)
            )
        else:
            log.error(
                "%s Async loop not available. Cannot process message on topic: %s",
                self.log_identifier,
                topic,
            )
            raise RuntimeError("Async loop not available for message processing")

    def _handle_async_message_completion(self, future: asyncio.Future, topic: str):
        """Callback to handle completion of async message processing."""
        try:
            if future.cancelled():
                log.warning(
                    "%s Message processing for topic %s was cancelled.",
                    self.log_identifier,
                    topic,
                )
            elif future.done():
                exception = future.exception()
                if exception is not None:
                    log.error(
                        "%s Message processing for topic %s failed: %s",
                        self.log_identifier,
                        topic,
                        exception,
                        exc_info=exception,
                    )
                else:
                    # Handle successful completion
                    try:
                        _ = future.result()
                        log.debug(
                            "%s Message processing for topic %s completed successfully.",
                            self.log_identifier,
                            topic,
                        )
                        # Optional: Process the result if needed
                        # self._process_successful_result(result, topic)
                    except Exception as result_exception:
                        # This catches exceptions that might occur when getting the result
                        log.error(
                            "%s Error retrieving result for topic %s: %s",
                            self.log_identifier,
                            topic,
                            result_exception,
                            exc_info=result_exception,
                        )
            else:
                # This case shouldn't normally occur in a completion callback,
                # but it's good defensive programming
                log.warning(
                    "%s Future for topic %s is not done in completion handler.",
                    self.log_identifier,
                    topic,
                )
        except Exception as e:
            log.error(
                "%s Error in async message completion handler for topic %s: %s",
                self.log_identifier,
                topic,
                e,
                exc_info=True,
            )

    @abc.abstractmethod
    async def _handle_message_async(self, message, topic: str) -> None:
        """
        Async handler for incoming messages.

        Subclasses must implement this to process messages asynchronously.
        This runs on the component's dedicated async event loop.

        Args:
            message: The Solace message (SolaceMessage instance)
            topic: The topic the message was received on
        """
        pass

    def _late_init(self):
        """Late initialization hook called after the component is fully set up."""

        # Setup the Trust Manager if present (enterprise feature)
        # NOTE: The Trust Manager should use component.get_broker_username() to retrieve
        # the actual broker client-username for trust card topic construction. This is
        # critical because trust cards MUST be published on topics that match the actual
        # authentication identity (client-username) used to connect to the broker.
        try:
            from solace_agent_mesh_enterprise.common.trust import (
                initialize_trust_manager,
            )

            trust_config = self.get_config("trust_manager")
            if trust_config and trust_config.get("enabled", False):
                self.trust_manager = initialize_trust_manager(self)
                log.info("%s Enterprise Trust Manager initialized", self.log_identifier)
        except ImportError:
            log.debug("%s Enterprise Trust Manager not available", self.log_identifier)
        except Exception as e:
            log.error(
                "%s Failed to initialize Trust Manager: %s", self.log_identifier, e
            )

    def publish_a2a_message(
        self, payload: dict, topic: str, user_properties: dict | None = None
    ):
        """Helper to publish A2A messages via the SAC App with size validation."""
        try:
            log.debug(
                "%s [publish_a2a_message] Starting - topic: %s, payload keys: %s",
                self.log_identifier,
                topic,
                list(payload.keys()) if isinstance(payload, dict) else "not_dict"
            )

            # Create user_properties if it doesn't exist
            if user_properties is None:
                user_properties = {}
            
            user_properties["timestamp"] = int(time.time() * 1000)

            # Validate message size
            is_valid, actual_size = validate_message_size(
                payload, self.max_message_size_bytes, self.log_identifier
            )

            if not is_valid:
                error_msg = (
                    f"Message size validation failed: payload size ({actual_size} bytes) "
                    f"exceeds maximum allowed size ({self.max_message_size_bytes} bytes)"
                )
                log.error("%s [publish_a2a_message] %s", self.log_identifier, error_msg)
                raise MessageSizeExceededError(
                    actual_size, self.max_message_size_bytes, error_msg
                )

            # Debug logging to show message size when publishing
            log.debug(
                "%s [publish_a2a_message] Publishing message to topic %s (size: %d bytes)",
                self.log_identifier,
                topic,
                actual_size,
            )

            app = self.get_app()
            if app:
                log.debug(
                    "%s [publish_a2a_message] Got app instance, about to call app.send_message",
                    self.log_identifier
                )

                # Conditionally log to invocation monitor if it exists (i.e., on an agent)
                if hasattr(self, "invocation_monitor") and self.invocation_monitor:
                    self.invocation_monitor.log_message_event(
                        direction="PUBLISHED",
                        topic=topic,
                        payload=payload,
                        component_identifier=self.log_identifier,
                    )

                if trace_logger.isEnabledFor(logging.DEBUG):
                    trace_logger.debug(
                        "%s [publish_a2a_message] About to call app.send_message on topic '%s'\nwith payload: %s\nwith user_properties: %s",
                        self.log_identifier, topic, payload, user_properties
                    )
                else:
                    log.debug(
                        "%s [publish_a2a_message] About to call app.send_message on topic '%s' (for more details, enable TRACE logging)",
                        self.log_identifier, topic
                    )

                app.send_message(
                    payload=payload, topic=topic, user_properties=user_properties
                )

                log.debug(
                    "%s [publish_a2a_message] Successfully called app.send_message on topic '%s'",
                    self.log_identifier, topic
                )
            else:
                log.error(
                    "%s Cannot publish message: Not running within a SAC App context.",
                    self.log_identifier,
                )
        except MessageSizeExceededError:
            # Re-raise MessageSizeExceededError without wrapping
            raise
        except Exception as e:
            log.exception(
                "%s Failed to publish A2A message to topic %s: %s",
                self.log_identifier,
                topic,
                e,
            )
            raise

    def _run_async_operations(self):
        """Target for the dedicated async thread. Sets up and runs the event loop."""
        log.info(
            "%s Initializing asyncio event loop in dedicated thread...",
            self.log_identifier,
        )
        self._async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._async_loop)

        main_task = None
        try:
            log.info(
                "%s Starting _async_setup_and_run as an asyncio task. Will run event loop forever (or until stop_signal).",
                self.log_identifier,
            )
            main_task = self._async_loop.create_task(self._async_setup_and_run())

            self._async_loop.run_forever()

        except Exception as e:
            log.exception(
                "%s Unhandled exception in _run_async_operations: %s",
                self.log_identifier,
                e,
            )
            self.stop_signal.set()
        finally:
            if main_task and not main_task.done():
                log.info(
                    "%s Cancelling main async task (_async_setup_and_run).",
                    self.log_identifier,
                )
                main_task.cancel()
                try:
                    # Use gather to await the cancellation
                    self._async_loop.run_until_complete(
                        asyncio.gather(main_task, return_exceptions=True)
                    )
                except RuntimeError as loop_err:
                    log.warning(
                        "%s Error awaiting main task during cleanup (loop closed?): %s",
                        self.log_identifier,
                        loop_err,
                    )

            if self._async_loop.is_running():
                log.info(
                    "%s Stopping asyncio event loop from _run_async_operations finally block.",
                    self.log_identifier,
                )
                self._async_loop.stop()
            log.info(
                "%s Async operations loop finished in dedicated thread.",
                self.log_identifier,
            )

    def run(self):
        """Starts the component's dedicated async thread."""
        log.info("%s Starting SamComponentBase run method.", self.log_identifier)

        # Do all initialization that needs to be done after we are fully setup
        self._late_init()

        if not self._async_thread or not self._async_thread.is_alive():
            self._async_thread = threading.Thread(
                target=self._run_async_operations,
                name=f"{self.name}_AsyncOpsThread",
                daemon=True,
            )
            self._async_thread.start()
            log.info("%s Async operations thread started.", self.log_identifier)
        else:
            log.warning(
                "%s Async operations thread already running.", self.log_identifier
            )

        # Monitor async initialization without blocking (critical for multi-agent processes)
        if hasattr(self, '_async_init_future') and self._async_init_future is not None:
            log.info("%s Setting up async initialization monitoring...", self.log_identifier)

            def handle_init_completion(future):
                """Non-blocking callback for initialization completion."""
                try:
                    future.result()  # Raises if init failed
                    log.info("%s Async initialization completed successfully.", self.log_identifier)
                except Exception as init_error:
                    error_msg = f"{self.log_identifier} Async initialization failed: {init_error}"
                    log.error(error_msg, exc_info=init_error)
                    self.stop_signal.set()
                    self._async_init_error = ComponentInitializationError(
                        self.log_identifier, init_error, error_msg
                    )

            self._async_init_future.add_done_callback(handle_init_completion)
            log.info("%s Async initialization monitoring active (non-blocking).", self.log_identifier)

        super().run()
        log.info("%s SamComponentBase run method finished.", self.log_identifier)

    def cleanup(self):
        """Cleans up the component's resources, including the async thread and loop."""
        log.info("%s Starting cleanup for SamComponentBase...", self.log_identifier)

        try:
            self._pre_async_cleanup()
        except Exception as e:
            log.exception(
                "%s Error during _pre_async_cleanup(): %s", self.log_identifier, e
            )

        if self._async_loop and self._async_loop.is_running():
            log.info("%s Requesting asyncio loop to stop...", self.log_identifier)
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)

        if self._async_thread and self._async_thread.is_alive():
            log.info(
                "%s Joining async operations thread (timeout 10s)...",
                self.log_identifier,
            )
            self._async_thread.join(timeout=10)
            if self._async_thread.is_alive():
                log.warning(
                    "%s Async operations thread did not join cleanly.",
                    self.log_identifier,
                )

        if self._async_loop and not self._async_loop.is_closed():
            log.info(
                "%s Closing asyncio event loop (if not already closed by its thread).",
                self.log_identifier,
            )
            # The loop should have been stopped by its own thread's finally block.
            # We just need to close it from this thread.
            self._async_loop.call_soon_threadsafe(self._async_loop.close)

        super().cleanup()
        log.info("%s SamComponentBase cleanup finished.", self.log_identifier)

    def get_async_loop(self) -> asyncio.AbstractEventLoop | None:
        """Returns the dedicated asyncio event loop for this component's async tasks."""
        return self._async_loop

    def get_broker_username(self) -> Optional[str]:
        """
        Returns the broker username (client-username) that this component uses
        to authenticate with the Solace broker.

        This is critical for trust card publishing and verification, as the
        trust card topic must match the actual authentication identity.

        Returns:
            The broker username if available, None otherwise.
        """
        try:
            app = self.get_app()
            if app and hasattr(app, "app_info"):
                broker_config = app.app_info.get("broker", {})
                broker_username = broker_config.get("broker_username")
                if broker_username:
                    log.debug(
                        "%s Retrieved broker username: %s",
                        self.log_identifier,
                        broker_username,
                    )
                    return broker_username
                else:
                    log.warning(
                        "%s Broker username not found in broker configuration",
                        self.log_identifier,
                    )
            else:
                log.warning(
                    "%s Unable to access app or app_info to retrieve broker username",
                    self.log_identifier,
                )
        except Exception as e:
            log.error(
                "%s Error retrieving broker username: %s",
                self.log_identifier,
                e,
                exc_info=True,
            )
        return None

    @abc.abstractmethod
    def _get_component_id(self) -> str:
        """
        Returns unique identifier for this component instance.
        Must be implemented by subclasses.

        Returns:
            Unique component identifier (e.g., agent_name, gateway_id)
        """
        pass

    @abc.abstractmethod
    def _get_component_type(self) -> str:
        """
        Returns component type string.
        Must be implemented by subclasses.

        Returns:
            Component type ("gateway", "agent", etc.)
        """
        pass

    async def _async_setup_and_run(self) -> None:
        """
        Base async setup that initializes Trust Manager if present.
        Subclasses should override and call super() first, then add their logic.
        """
        # Initialize Trust Manager if present (ENTERPRISE FEATURE)
        if self.trust_manager:
            try:
                log.info(
                    "%s Initializing Trust Manager with periodic publishing...",
                    self.log_identifier,
                )
                # Pass event loop and add_timer method to Trust Manager
                await self.trust_manager.initialize(
                    add_timer_callback=self.add_timer,
                    event_loop=self.get_async_loop(),
                )
                log.info(
                    "%s Initialized Trust Manager", self.log_identifier
                )
            except Exception as e:
                log.error(
                    "%s Failed to initialize Trust Manager: %s",
                    self.log_identifier,
                    e,
                    exc_info=True,
                )
                # Trust Manager failure should not prevent component startup
                # Set to None to disable trust manager for this session
                self.trust_manager = None

    @abc.abstractmethod
    def _pre_async_cleanup(self) -> None:
        """
        Abstract method for subclasses to perform cleanup actions
        before the async loop is stopped.
        """
        pass
