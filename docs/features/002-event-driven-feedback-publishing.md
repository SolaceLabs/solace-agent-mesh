# Feature: Event-Driven Feedback Publishing

**Version:** 1.0
**Status:** Proposed

## 1. Background

Currently, user feedback submitted through the WebUI is captured and stored directly in the WebUI Gateway's internal database. While this provides a persistent record for historical review via the API, it creates a data silo. The feedback is not easily accessible in real-time to other systems, and integrating it with external analytics, monitoring, or alerting platforms requires direct database access or polling the gateway's API.

This approach limits the immediate value of user feedback and creates a tight coupling between the feedback data and the gateway's persistence layer.

## 2. Goals and Purpose

The primary goal of this feature is to transform user feedback from a passive, stored data point into a first-class, real-time event within the Solace Agent Mesh ecosystem. By publishing feedback events to the message broker, we can decouple the gateway from feedback consumers and enable a wide range of new integrations.

The key purposes are:

-   **Decouple Feedback:** Separate the act of collecting feedback from the act of consuming it.
-   **Enable Real-Time Integration:** Allow external systems (e.g., analytics dashboards, alerting tools, data lakes) to subscribe to and react to user feedback as it happens.
-   **Enhance Observability:** Treat user feedback as a critical operational event that can be monitored and correlated with other system metrics.
-   **Maintain Architectural Consistency:** Align feedback handling with the event-driven principles of the broader system by utilizing the message broker for event distribution.

## 3. Requirements

### R1: Configurable Publishing Mechanism

-   **R1.1:** A mechanism shall be created within the WebUI Gateway to publish user feedback as an event to the message broker.
-   **R1.2:** This feature shall be controlled by a static configuration flag (`enabled`). If disabled, no events will be published.
-   **R1.3:** The Solace topic for publishing feedback events shall be fully configurable.
-   **R1.4:** The existing behavior of storing feedback in the local database shall be preserved and operate in parallel with the new publishing mechanism.

### R2: Flexible and Context-Rich Payload

-   **R2.1:** The published event payload shall be a structured, versionable JSON object.
-   **R2.2:** The system shall provide a configuration option (`include_task_info`) to control the amount of associated task context included in the event payload.
-   **R2.3:** The `include_task_info` option shall support the following levels of detail:
    -   **`none`**: The payload contains only the feedback data (e.g., task ID, rating, comment, user ID).
    -   **`summary`**: The payload contains the feedback data plus a summary of the task, including the initial request text, timestamps, and final status.
    -   **`stim`**: The payload contains the feedback data plus the complete task history, formatted as a `.stim` file structure (invocation details and full event flow).

### R3: Robust Payload Size Management

-   **R3.1:** The system shall provide a configuration option (`max_payload_size_bytes`) to define a maximum size for the feedback event payload to prevent exceeding broker limits.
-   **R3.2:** If `include_task_info` is configured to `stim` and the resulting payload size exceeds the configured `max_payload_size_bytes`, the system shall automatically fall back to the `summary` level of detail.
-   **R3.3:** When a fallback occurs due to payload size, the published payload shall include a `truncation_details` object that clearly indicates that a fallback occurred and why.

### R4: System Integration

-   **R4.1:** The feedback publishing mechanism shall reuse the existing, underlying broker client and connection managed by the WebUI Gateway component. No new client connections shall be created.

## 4. Decisions Made

The following architectural and terminological decisions have been agreed upon:

-   **Fallback Over Truncation:** To handle oversized payloads when using the `stim` option, the system will fall back to the `summary` level rather than attempting to surgically truncate the complex `.stim` object. This approach is simpler, more robust, and guarantees a valid, useful event is always published.
-   **Parallel Persistence:** The new event publishing feature is an enhancement, not a replacement. The existing functionality of saving feedback to the gateway's database will be maintained to support the gateway's own historical task review features.
-   **Configuration Grouping:** All configuration for this feature will be grouped under a new `feedback_publishing` block within the gateway's `app_config` to keep it logically separate from other features like `task_logging`.
-   **Broker Client Reuse:** The feature will be implemented within the `FeedbackService` and will leverage the existing `publish_a2a` method provided by the `WebUIBackendComponent`, ensuring no new broker clients or connections are needed.
