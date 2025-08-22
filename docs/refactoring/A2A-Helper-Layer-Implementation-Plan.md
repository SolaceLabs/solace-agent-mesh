# Implementation Plan: A2A Helper Abstraction Layer

This document provides a step-by-step plan for creating the A2A Helper Abstraction Layer. This phase focuses exclusively on the creation of the new helper modules and functions. Refactoring existing code to *use* these helpers will be handled in a subsequent phase.

---

## Phase 1: Create the Package Structure

The first step is to create the new directory structure that will house our organized helper modules.

*   **Step 1.1:** Create a new directory: `src/solace_agent_mesh/common/a2a/`.
*   **Step 1.2:** Create an empty `__init__.py` file inside this new directory to mark it as a Python package.

---

## Phase 2: Populate the Helper Modules

We will now create each module as defined in our design document and populate it with the initial set of helper functions.

*   **Step 2.1: Create `a2a/protocol.py`**
    *   **Responsibility:** Handle the "envelope" and "transport" aspects of A2A, including topic construction and parsing JSON-RPC requests/responses.
    *   **Actions:**
        *   Move all topic-related functions (e.g., `get_agent_request_topic`, `get_discovery_topic`) from `src/solace_agent_mesh/common/a2a_protocol.py` into this new file.
        *   Add new helper functions for safely parsing the JSON-RPC envelope, ensuring they are non-leaky abstractions (i.e., they accept the top-level `A2ARequest`/`JSONRPCResponse` objects).

*   **Step 2.2: Create `a2a/message.py`**
    *   **Responsibility:** All logic for creating and consuming `Message` and `Part` objects.
    *   **Actions:**
        *   Create helper functions like `create_agent_text_message`, `create_agent_data_message`, etc.
        *   Create consumption helpers like `get_text_from_message`, `get_data_parts_from_message`, etc. These will internally use the `a2a-sdk` utilities but provide a consistent API for our application.

*   **Step 2.3: Create `a2a/task.py`**
    *   **Responsibility:** All logic for creating and consuming `Task` objects.
    *   **Actions:**
        *   Create helpers like `create_initial_task` and `get_task_id`.

*   **Step 2.4: Create `a2a/artifact.py`**
    *   **Responsibility:** All logic for creating and consuming `Artifact` objects.
    *   **Actions:**
        *   Create helpers like `create_text_artifact` and `get_artifact_id`.

*   **Step 2.5: Create `a2a/events.py`**
    *   **Responsibility:** All logic for creating and consuming asynchronous event objects like `TaskStatusUpdateEvent`.
    *   **Actions:**
        *   Create helpers like `create_status_update_event` and `get_message_from_status_update`.

*   **Step 2.6: Create `a2a/translation.py`**
    *   **Responsibility:** Isolate the logic for translating between A2A objects and other domains (e.g., Google ADK).
    *   **Actions:**
        *   Move the existing `translate_a2a_to_adk_content` and `format_adk_event_as_a2a` functions from `src/solace_agent_mesh/common/a2a_protocol.py` into this new file.

---

## Phase 3: Finalize the Package and Clean Up

*   **Step 3.1: Populate the `a2a/__init__.py` file**
    *   **Responsibility:** Expose a clean, public API for the rest of the application.
    *   **Action:** Add imports to this file to expose the most commonly used helper functions from the other modules. This will allow developers to use cleaner imports, like `from ...common.a2a import create_agent_text_message`.

*   **Step 3.2: Deprecate the old `a2a_protocol.py`**
    *   **Action:** Once all functions have been moved out of `src/solace_agent_mesh/common/a2a_protocol.py`, the file will be deleted.
