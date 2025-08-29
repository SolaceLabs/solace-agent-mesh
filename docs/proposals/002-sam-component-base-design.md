# Detailed Design: `SamComponentBase`

## 1. Introduction

This document provides the detailed design for the `SamComponentBase` refactoring, as outlined in the corresponding proposal. The goal is to create a shared base class for `SamAgentComponent` and `BaseGatewayComponent` to centralize common logic for asynchronous operations and message publishing.

## 2. `SamComponentBase` Class Design

A new abstract base class, `SamComponentBase`, will be created at `src/solace_agent_mesh/common/sac/sam_component_base.py`.

### 2.1. Inheritance and Purpose

`SamComponentBase` will inherit from `solace_ai_connector.components.component_base.ComponentBase` and `abc.ABC`. It will serve as the parent class for high-level SAM components, providing a standardized framework for:
- Managing a dedicated `asyncio` event loop running in a separate thread.
- Publishing A2A messages with built-in size validation.

### 2.2. Properties

The base class will manage the following key properties:

- `namespace: str`: The A2A namespace, initialized from configuration.
- `max_message_size_bytes: int`: The maximum allowed size for outgoing messages, initialized from configuration.
- `_async_loop: Optional[asyncio.AbstractEventLoop]`: The event loop running in the dedicated thread.
- `_async_thread: Optional[threading.Thread]`: The dedicated thread for running the async loop.

### 2.3. Constructor (`__init__`)

The constructor will:
- Call `super().__init__()`.
- Initialize `self.namespace` and `self.max_message_size_bytes` from the component configuration.
- Initialize `self._async_loop` and `self._async_thread` to `None`.

### 2.4. Asynchronous Lifecycle Management

The base class will fully manage the async thread and event loop lifecycle.

- **`run(self)`**:
    - Overrides the parent method.
    - Creates and starts the `_async_thread`, setting its target to `self._run_async_operations`.
    - Calls `super().run()`.

- **`_run_async_operations(self)`**:
    - This is the main function executed in the `_async_thread`.
    - It creates a new `asyncio` event loop and assigns it to `self._async_loop`.
    - It calls the abstract method `_async_setup_and_run()` which subclasses must implement to perform their specific asynchronous work.
    - It runs the event loop until it is stopped.
    - It handles the final cleanup of the loop.

- **`cleanup(self)`**:
    - Overrides the parent method.
    - Calls the abstract method `_pre_async_cleanup()` for subclass-specific cleanup before the loop is stopped.
    - Stops the `_async_loop` in a thread-safe manner.
    - Joins the `_async_thread` with a timeout.
    - Calls `super().cleanup()`.

- **`get_async_loop(self) -> Optional[asyncio.AbstractEventLoop]`**:
    - A public method to provide access to the component's dedicated event loop.

### 2.5. Shared Functionality

- **`publish_a2a_message(self, payload: Dict, topic: str, user_properties: Optional[Dict] = None)`**:
    - This method will contain the complete logic for publishing messages.
    - It will use `common.utils.message_utils.validate_message_size` to check the payload against `self.max_message_size_bytes`.
    - It will raise a `MessageSizeExceededError` if validation fails.
    - It will conditionally check for `hasattr(self, 'invocation_monitor')` and, if present, call `self.invocation_monitor.log_message_event()` to support agent-specific monitoring without creating a hard dependency.
    - It will use `self.get_app().send_message()` to publish the message.

### 2.6. Abstract Methods

Subclasses will be required to implement the following methods:

- **`@abstractmethod async def _async_setup_and_run(self) -> None:`**:
    - **Purpose**: To execute the component-specific asynchronous logic within the managed event loop.
    - **Implementation**:
        - `SamAgentComponent`: Will implement this to call `self._perform_async_init()`.
        - `BaseGatewayComponent`: Will implement this to call `self._start_listener()` and then create and await the `self._message_processor_loop()` task.

- **`@abstractmethod def _pre_async_cleanup(self) -> None:`**:
    - **Purpose**: To perform any necessary cleanup actions before the async loop is stopped during the `cleanup` sequence.
    - **Implementation**:
        - `SamAgentComponent`: Can be a `pass` implementation if no specific pre-cleanup is needed.
        - `BaseGatewayComponent`: Will implement this to call `self._stop_listener()`.

## 3. `SamAgentComponent` Refactoring

### 3.1. Inheritance

- The class will be modified to inherit from `SamComponentBase`.

### 3.2. Removed Logic

The following methods and initialization logic will be removed, as they are now handled by the base class:
- `_publish_a2a_message`
- `_start_async_loop`
- `_async_loop`, `_async_thread`, `_async_init_future` initialization in `__init__`.
- The thread and loop management parts of `cleanup`.

### 3.3. Implementation of Abstract Methods

- **`_async_setup_and_run`**: Will be implemented to `await self._perform_async_init()`.
- **`_pre_async_cleanup`**: Will be implemented as a `pass` method, as the agent's current cleanup logic fits within the standard `cleanup` flow.

## 4. `BaseGatewayComponent` Refactoring

### 4.1. Inheritance

- The class will be modified to inherit from `SamComponentBase`.

### 4.2. Removed/Modified Logic

- The `run`, `cleanup`, and `_run_async_operations` methods will be removed.
- The `publish_a2a_message` method will be removed and inherited from the base class.
- Initialization of `_async_loop` and `_async_thread` will be removed from `__init__`.

### 4.3. Implementation of Abstract Methods

- **`_async_setup_and_run`**: Will be implemented to:
    1. Call `self._start_listener()`.
    2. Create and `await` the task for `self._message_processor_loop()`.
- **`_pre_async_cleanup`**: Will be implemented to call `self._stop_listener()`.

### 4.4. Configuration

- The gateway's configuration schema must be updated to include a `max_message_size_bytes` parameter to support the inherited `publish_a2a_message` method.
