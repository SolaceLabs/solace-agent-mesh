"""
Base Component class for SAM implementations in the Solace AI Connector.
"""

import abc
import asyncio
import threading
from typing import Any

from solace_ai_connector.common.log import log
from solace_ai_connector.components.component_base import ComponentBase

from ..exceptions import MessageSizeExceededError
from ..utils.message_utils import validate_message_size


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
        log.info("%s SamComponentBase initialized successfully.", self.log_identifier)

    def publish_a2a_message(
        self, payload: dict, topic: str, user_properties: dict | None = None
    ):
        """Helper to publish A2A messages via the SAC App with size validation."""
        try:
            log.debug(
                f"{self.log_identifier} [publish_a2a_message] Starting - topic: {topic}, payload keys: {list(payload.keys()) if isinstance(payload, dict) else 'not_dict'}"
            )

            # Validate message size
            is_valid, actual_size = validate_message_size(
                payload, self.max_message_size_bytes, self.log_identifier
            )

            if not is_valid:
                error_msg = (
                    f"Message size validation failed: payload size ({actual_size} bytes) "
                    f"exceeds maximum allowed size ({self.max_message_size_bytes} bytes)"
                )
                log.error("%s %s", self.log_identifier, error_msg)
                raise MessageSizeExceededError(
                    actual_size, self.max_message_size_bytes, error_msg
                )

            # Debug logging to show message size when publishing
            log.debug(
                "%s Publishing message to topic %s (size: %d bytes)",
                self.log_identifier,
                topic,
                actual_size,
            )

            app = self.get_app()
            if app:
                log.debug(
                    f"{self.log_identifier} [publish_a2a_message] Got app instance, about to call app.send_message"
                )

                # Conditionally log to invocation monitor if it exists (i.e., on an agent)
                if hasattr(self, "invocation_monitor") and self.invocation_monitor:
                    self.invocation_monitor.log_message_event(
                        direction="PUBLISHED",
                        topic=topic,
                        payload=payload,
                        component_identifier=self.log_identifier,
                    )

                log.debug(
                    f"{self.log_identifier} [publish_a2a_message] About to call app.send_message with payload: {payload}"
                )
                log.debug(
                    f"{self.log_identifier} [publish_a2a_message] App send_message params - topic: {topic}, user_properties: {user_properties}"
                )

                app.send_message(
                    payload=payload, topic=topic, user_properties=user_properties
                )

                log.debug(
                    f"{self.log_identifier} [publish_a2a_message] Successfully called app.send_message"
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
                "%s Starting _async_setup_and_run as an asyncio task.",
                self.log_identifier,
            )
            main_task = self._async_loop.create_task(self._async_setup_and_run())

            log.info(
                "%s Running asyncio event loop forever (or until stop_signal).",
                self.log_identifier,
            )
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

    @abc.abstractmethod
    async def _async_setup_and_run(self) -> None:
        """
        Abstract method for subclasses to implement their main asynchronous logic.
        This coroutine is executed within the managed event loop.
        """
        pass

    @abc.abstractmethod
    def _pre_async_cleanup(self) -> None:
        """
        Abstract method for subclasses to perform cleanup actions
        before the async loop is stopped.
        """
        pass
