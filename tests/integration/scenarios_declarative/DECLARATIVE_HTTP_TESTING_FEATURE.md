# Feature: Declarative HTTP API Testing

This document describes a planned enhancement to the declarative (YAML-based) integration testing framework to natively support HTTP API interactions with the Web UI backend.

## 1. Overview

The declarative test framework will be extended to allow test scenarios to be initiated via HTTP requests and to perform assertions by making subsequent HTTP requests to the Web UI's API endpoints. This integrates API-level testing directly into our high-fidelity, multi-agent testing environment.

## 2. Motivation

Currently, our integration tests are split into two distinct environments:

1.  **Declarative Scenarios (`tests/integration/scenarios_declarative`):** A powerful, high-fidelity environment that runs a real broker and multiple agent components. It is excellent for testing A2A message flows but currently lacks the ability to interact with the Web UI's HTTP API.
2.  **API Tests (`tests/integration/apis`):** A separate, isolated environment for testing the Web UI's FastAPI endpoints. This environment relies on heavily mocked components and has no connection to a real message broker, making it unsuitable for testing features that depend on event-driven communication (e.g., task logging).

This separation creates challenges. The API test environment is brittle and requires complex mocks that are difficult to maintain. The declarative environment, while more realistic, cannot validate the correctness of the HTTP API layer.

By integrating HTTP testing into the declarative framework, we can create a single, unified testing environment that enables true end-to-end validation of the entire system.

## 3. Key Capabilities

### 3.1. HTTP Request Initiation

Tests will be able to start not just by simulating an A2A message via `gateway_input`, but also by simulating a direct HTTP request to the Web UI backend.

A new `http_request_input` block will be added to the YAML schema, allowing the test author to specify:
-   HTTP Method (e.g., `POST`, `GET`)
-   Request Path (e.g., `/api/v1/message:stream`)
-   JSON Body
-   Query Parameters
-   File Uploads

**Example:**
```yaml
http_request_input:
  method: "POST"
  path: "/api/v1/message:stream"
  json_body:
    jsonrpc: "2.0"
    id: "req-123"
    method: "message/stream"
    params:
      message:
        role: "user"
        parts: [{kind: "text", text: "Hello from an HTTP request"}]
        metadata: {agent_name: "TestAgent"}
```

### 3.2. HTTP Response Assertions

At the conclusion of a test scenario, we will be able to make one or more HTTP requests to the API to assert on the final state of the system. This is ideal for verifying that an action (like creating a task) resulted in the correct data being persisted and made available via a `GET` endpoint.

A new `expected_http_responses` block will be added, allowing assertions on:
-   Expected HTTP Status Code
-   Expected JSON response body (using the existing subset matching logic)
-   Whether a response body is an empty list or object

**Example:**
```yaml
expected_http_responses:
  - description: "Verify the created task is visible in the tasks list"
    request:
      method: "GET"
      path: "/api/v1/tasks"
    expected_status_code: 200
    expected_json_body_matches:
      - id: "task-123"
        initial_request_text: "Hello from an HTTP request"
        status: "completed"
```

## 4. Benefits

-   **Unified Test Environment:** Eliminates the need for a separate, heavily mocked API testing suite.
-   **True End-to-End Testing:** Allows a single test case to validate the entire flow from an HTTP request to the agent, through the broker, to the database, and back out through another API call.
-   **Simplified Test Authoring:** Enables writing complex end-to-end tests in a simple, readable, and declarative YAML format.
-   **Increased Reliability:** Reduces reliance on brittle mocks, leading to more robust and trustworthy tests.
