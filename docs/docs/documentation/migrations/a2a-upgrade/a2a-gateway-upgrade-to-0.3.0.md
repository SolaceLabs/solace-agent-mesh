---
title: "Migration Guide: Upgrading to the A2A SDK"
sidebar_position: 10
---

This guide is for developers who have built or are maintaining a custom Agent Mesh gateway. A recent architectural update has aligned Agent Mesh with the official Agent-to-Agent (A2A) protocol specification by adopting the `a2a-sdk`. This migration requires some changes to your gateway code to ensure compatibility.

This document provides a high-level overview of the conceptual changes and a practical checklist to guide you through the upgrade process.

## Why the Change?

The migration from our legacy A2A implementation to the official `a2a-sdk` is a foundational improvement with several key benefits:

*   **Protocol Compliance:** Ensures your gateway is fully interoperable with any A2A-compliant agent or system.
*   **Standardization:** Replaces bespoke code with a community-supported standard, reducing technical debt.
*   **Improved Maintainability:** Insulates your gateway from future A2A specification changes. The `a2a-sdk` will be updated, not your core logic.
*   **Future-Proofing:** Positions your gateway to easily adopt new features as the A2A protocol evolves.

## Core Conceptual Changes

The upgrade introduces a few key changes in how you interact with A2A objects.

### The `a2a` Helper Layer: The New Best Practice

The most significant change is the introduction of a new abstraction layer located at `solace_agent_mesh.common.a2a`.

You should **no longer instantiate `a2a.types` models directly** or access their properties by hand. Instead, use the provided helper functions. This layer is designed to simplify development and protect your code from future SDK changes.

**Example:**

```python

# BEFORE: Direct instantiation and property access
from solace_agent_mesh.common.types import TextPart, Task
my_part = TextPart(text="Hello")
task_id = my_task.id

# AFTER: Using the a2a helper layer
from solace_agent_mesh.common import a2a
my_part = a2a.create_text_part(text="Hello")
task_id = a2a.get_task_id(my_task)

```

### Type System Migration

*   The legacy types in `solace_agent_mesh.common.types` (like `A2APart`, `FileContent`) are deprecated.
*   All A2A models now come from the `a2a.types` library.
*   The type hint for a list of message parts has changed from `List[A2APart]` to `List[ContentPart]`. `ContentPart` is a simple alias for the union of `TextPart`, `DataPart`, and `FilePart`.

### Accessing Object Properties

Field names on many A2A objects have changed. Always use the `a2a` helper functions for safe and future-proof access.

| Action | Old Pattern | New Pattern (Recommended) |
| :--- | :--- | :--- |
| Get Task ID | `task.id` | `a2a.get_task_id(task)` |
| Get Task Status | `task.status.state` | `a2a.get_task_status(task)` |
| Get Event's Task ID | `event.id` | `event.task_id` |
| Get Message Parts | `message.parts` | `a2a.get_parts_from_message(message)` |
| Get Error Message | `error.message` | `a2a.get_error_message(error)` |
| Get Error Code | `error.code` | `a2a.get_error_code(error)` |
| Get Error Data | `error.data` | `a2a.get_error_data(error)` |

### Changes to `BaseGatewayComponent`

The `BaseGatewayComponent` has been significantly improved. It now handles more of the A2A protocol complexity, simplifying gateway implementations.

*   **Artifact Handling:** The base class can now automatically handle artifact URIs, converting them to embedded bytes before sending them to your gateway's `_send_...` methods. This is controlled by the `resolve_artifact_uris_in_gateway` parameter in the constructor.
*   **Message Publishing:** The base class now manages the details of preparing and publishing the A2A request message in `submit_a2a_task`.
*   **Asynchronous Model:** The underlying threading model has been removed in favor of a more direct `asyncio` implementation, simplifying the component lifecycle.

It is highly recommended to review the latest `BaseGatewayComponent` and re-base your custom gateway on it to inherit these benefits and reduce boilerplate code.

## Migration Checklist

Follow these steps to update your gateway code.

1.  **Update Imports:**
    *   Remove imports from `solace_agent_mesh.common.types`.
    *   Add imports from `a2a.types` for specific models if needed.
    *   Add `from solace_agent_mesh.common import a2a`.
    *   Add `from solace_agent_mesh.common.a2a import ContentPart`.

2.  **Update Type Hints:**
    *   Find all instances of `List[A2APart]` and change them to `List[ContentPart]`.

3.  **Refactor Object Creation:**
    *   Replace direct model instantiation like `TextPart(...)` or `FilePart(...)` with their corresponding helper functions: `a2a.create_text_part(...)`, `a2a.create_file_part_from_uri(...)`, etc.

4.  **Refactor Property Access:**
    *   Replace direct property access (`task.id`, `error.message`) with calls to the `a2a` helper functions (`a2a.get_task_id(task)`, `a2a.get_error_message(error)`).

5.  **Review Base Class Integration:**
    *   If you have a custom gateway, compare it against the latest `BaseGatewayComponent`. Consider refactoring to delegate more responsibility (like artifact handling and message submission) to the base class.

6.  **Test Thoroughly:**
    *   Once refactored, run your integration tests to ensure the gateway correctly translates inputs and processes outputs in the new format.

## Code Examples: Before & After

Here are some common patterns you will encounter during the migration.

### Example 1: Translating External Input

This example shows how to create A2A parts from an external event.

<details>
<summary><strong>_translate_external_input</strong></summary>

**Before:**
```python
from solace_agent_mesh.common.types import Part as A2APart, TextPart, FilePart, FileContent

async def _translate_external_input(self, external_event: Any) -> Tuple[str, List[A2APart], Dict[str, Any]]:
    # ...
    a2a_parts: List[A2APart] = []

    # Create a file part with a URI
    uri = "artifact://..."
    a2a_parts.append(
        FilePart(
            file=FileContent(name="report.pdf", uri=uri)
        )
    )

    # Create a text part
    prompt = "Summarize the attached file."
    a2a_parts.append(TextPart(text=prompt))

    return "summary_agent", a2a_parts, {}
```

**After:**
```python
from solace_agent_mesh.common import a2a
from solace_agent_mesh.common.a2a import ContentPart

async def _translate_external_input(self, external_event: Any) -> Tuple[str, List[ContentPart], Dict[str, Any]]:
    # ...
    a2a_parts: List[ContentPart] = []

    # Create a file part with a URI using the helper
    uri = "artifact://..."
    file_part = a2a.create_file_part_from_uri(uri=uri, name="report.pdf")
    a2a_parts.append(file_part)

    # Create a text part using the helper
    prompt = "Summarize the attached file."
    text_part = a2a.create_text_part(text=prompt)
    a2a_parts.append(text_part)

    return "summary_agent", a2a_parts, {}
```
</details>

### Example 2: Sending a Final Response

This example shows how to process a final `Task` object.

<details>
<summary><strong>_send_final_response_to_external</strong></summary>

**Before:**
```python
from solace_agent_mesh.common.types import Task, TaskState, TextPart

async def _send_final_response_to_external(self, context: Dict, task_data: Task) -> None:
    task_id = task_data.id
    final_status_text = ":checkered_flag: Task complete."

    if task_data.status.state == TaskState.FAILED:
        error_message_text = ""
        if task_data.status.message and task_data.status.message.parts:
            for part in task_data.status.message.parts:
                if isinstance(part, TextPart):
                    error_message_text = part.text
                    break
        final_status_text = f":x: Error: Task failed. {error_message_text}".strip()

    # ... use final_status_text and task_id
```

**After:**
```python
from solace_agent_mesh.common import a2a
from a2a.types import Task, TaskState

async def _send_final_response_to_external(self, context: Dict, task_data: Task) -> None:
    # Use helpers to safely access properties
    task_id = a2a.get_task_id(task_data)
    task_status = a2a.get_task_status(task_data)

    final_status_text = ":checkered_flag: Task complete."

    if task_status == TaskState.failed:
        error_message_text = ""
        if task_data.status and task_data.status.message:
            # Use helper to extract all text from the message
            error_message_text = a2a.get_text_from_message(task_data.status.message)
        final_status_text = f":x: Error: Task failed. {error_message_text}".strip()

    # ... use final_status_text and task_id
```
</details>
