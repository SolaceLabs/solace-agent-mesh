# Implementation Plan: `SamComponentBase` Refactoring

This document outlines the step-by-step plan to implement the `SamComponentBase` refactoring.

## 1. Create `SamComponentBase` Class

-   **Action:** Create a new file `src/solace_agent_mesh/common/sac/sam_component_base.py`.
-   **Details:**
    -   Define the `SamComponentBase` class inheriting from `solace_ai_connector.components.component_base.ComponentBase` and `abc.ABC`.
    -   Implement the `__init__` method. It will call `super().__init__()` and initialize common properties from the component's configuration:
        -   `self.namespace: str`
        -   `self.max_message_size_bytes: int`
        -   `self._async_loop: Optional[asyncio.AbstractEventLoop] = None`
        -   `self._async_thread: Optional[threading.Thread] = None`
    -   Move the asynchronous lifecycle management logic from `BaseGatewayComponent` and `SamAgentComponent` into `SamComponentBase`. This includes:
        -   `run(self)`: To start the `_async_thread`.
        -   `_run_async_operations(self)`: The target for the thread, which creates and runs the `asyncio` event loop.
        -   `cleanup(self)`: To stop the loop and join the thread.
        -   `get_async_loop(self)`: A public accessor for the event loop.
    -   Define two abstract methods that subclasses must implement:
        -   `@abstractmethod async def _async_setup_and_run(self) -> None:`
        -   `@abstractmethod def _pre_async_cleanup(self) -> None:`
    -   Move the `_publish_a2a_message` method from `SamAgentComponent` into `SamComponentBase` and rename it to `publish_a2a_message`.
    -   Modify the moved `publish_a2a_message` to be generic:
        -   It must conditionally check for the existence of `self.invocation_monitor` using `hasattr()` before attempting to call it. This ensures it works for both agents (which have it) and gateways (which do not).

## 2. Update Gateway Configuration

-   **Action:** Modify `src/solace_agent_mesh/gateway/base/app.py`.
-   **Details:**
    -   Add a new parameter definition for `gateway_max_message_size_bytes` to the `BASE_GATEWAY_APP_SCHEMA` dictionary. Set a reasonable default (e.g., 10MB).
    -   In the `__init__` method, read this new configuration value and ensure it's passed down to the component's `app_config`.

## 3. Refactor `BaseGatewayComponent`

-   **Action:** Modify `src/solace_agent_mesh/gateway/base/component.py`.
-   **Details:**
    -   Change the class signature to inherit from `SamComponentBase`.
    -   Update `__init__` to call `super().__init__()`. Remove the manual initialization of `self.async_loop` and `self.async_thread`.
    -   Remove the `run`, `cleanup`, `_run_async_operations`, and `publish_a2a_message` methods, as they are now inherited.
    -   Implement the `_async_setup_and_run` abstract method. This method's body will contain the logic to call `self._start_listener()` and create the `self._message_processor_loop()` task.
    -   Implement the `_pre_async_cleanup` abstract method. This method's body will contain the call to `self._stop_listener()`.

## 4. Refactor `SamAgentComponent`

-   **Action:** Modify `src/solace_agent_mesh/agent/sac/component.py`.
-   **Details:**
    -   Change the class signature to inherit from `SamComponentBase`.
    -   Update `__init__` to call `super().__init__()`. Remove the manual initialization of `self._async_loop`, `self._async_thread`, and `self._async_init_future`.
    -   Remove the `_start_async_loop` method and the async-related logic from the `cleanup` method.
    -   Remove the `_publish_a2a_message` method.
    -   Perform a search-and-replace within the file to change all calls from `self._publish_a2a_message(...)` to `self.publish_a2a_message(...)`.
    -   Implement the `_async_setup_and_run` abstract method. Its body will be `await self._perform_async_init()`.
    -   Implement the `_pre_async_cleanup` abstract method with a `pass` statement, as no pre-cleanup actions are currently required for the agent.

## 5. Add `update_artifact_parts` Utility

-   **Action:** Modify `src/solace_agent_mesh/common/a2a/artifact.py`.
-   **Details:**
    -   Add a new function `update_artifact_parts(artifact: Artifact, new_parts: List[ContentPart]) -> Artifact`. This function will return a new `Artifact` instance with its `parts` attribute replaced by the `new_parts`.
-   **Action:** Modify `src/solace_agent_mesh/common/a2a/__init__.py`.
-   **Details:**
    -   Export the new `update_artifact_parts` function in the `__all__` list.

## 6. Update Documentation

-   **Action:** Modify `docs/proposals/002-sam-component-base-design.md`.
-   **Details:**
    -   In section 2.5, change the method name from `publish_a2a_message(self, payload: Dict, topic: str, user_properties: Optional[Dict] = None)` to reflect its new public status and correct signature.
-   **Action:** Modify `src/solace_agent_mesh/common/a2a/a2a_llm.txt`.
-   **Details:**
    -   In the `artifact.py` section, add documentation for the new `update_artifact_parts` function.
