# Proposal: Frontend-Driven Inline Artifact Rendering

- **Status**: Proposed
- **Author**: AI Assistant
- **Date**: 2025-09-04

## 1. Summary

This document proposes a design for rendering certain types of file artifacts directly within the chat user interface. This feature will be driven primarily by the frontend, giving it the autonomy to decide what content to render inline and when to fetch the necessary data. The backend's role is to provide the raw `FilePart` data and a secure endpoint for on-demand content retrieval.

The goal is to enhance the user experience by displaying content like images, audio, and formatted text directly in the conversation flow, rather than always showing a generic file card.

## 2. Motivation

Currently, all file artifacts sent from an agent to the user are displayed as a generic file card with "view" and "download" icons. While functional, this creates a disjointed experience. For example, when an agent generates an image, the user has to click to view it in a separate tab.

By rendering content inline, we can create a more fluid and intuitive chat experience, making the agent's output immediately accessible and useful.

## 3. Design Principles

-   **Frontend Autonomy**: The frontend application (e.g., the Web UI) is the single source of truth for presentation logic. It decides which MIME types to render inline and how to display them.
-   **Backend as a Secure Data Provider**: The backend gateway's primary responsibility is to pass along the A2A `FilePart` objects as-is and provide a secure, authenticated endpoint for the frontend to fetch artifact content when needed.
-   **On-Demand Fetching**: To avoid large WebSocket payloads and give the frontend control, file content will be fetched on-demand via a standard HTTP request if it is not already embedded in the `FilePart`.
-   **Security First**: Internal `artifact://` URIs must never be directly accessible from the client. All data retrieval must be proxied through a secure, authenticated backend endpoint.

## 4. Detailed Design

The implementation is divided between backend prerequisites and frontend logic.

### 4.1. Backend Responsibilities (Gateway)

The backend's role is minimal and primarily involves providing a secure data access layer.

#### 4.1.1. Secure Artifact Download Endpoint

A new API endpoint will be created in the gateway's web server (e.g., `web_ui/app.py`).

-   **Endpoint**: `GET /api/v1/artifacts/download`
-   **Query Parameter**: `uri` (e.g., `/api/v1/artifacts/download?uri=artifact://...`)
-   **Logic**:
    1.  **Authentication & Authorization**: This is the most critical step. The endpoint MUST validate the user's session/token to ensure they are authenticated. It must then check if the authenticated user is authorized to access the specific artifact requested in the `uri` parameter. This prevents users from crafting URIs to access other users' data.
    2.  **Fetch Artifact**: Upon successful authorization, the endpoint uses the `shared_artifact_service` to load the raw bytes of the artifact.
    3.  **Stream Response**: The endpoint streams the file bytes back to the client with the appropriate `Content-Type` header and a `Content-Disposition: attachment; filename="..."` header to ensure it can be downloaded correctly.

#### 4.1.2. WebSocket Communication

The gateway backend will **not** change its existing logic for sending A2A events. It will continue to send `FilePart` objects within `TaskStatusUpdateEvent` or final `Task` objects over the WebSocket to the frontend exactly as it receives them from the agent.

### 4.2. Frontend Responsibilities (Web UI)

The majority of the implementation work resides in the frontend application.

#### 4.2.1. Smart File Rendering Component

The existing frontend component responsible for rendering file cards will be enhanced to become a "smart renderer".

-   **Input**: The component will receive a `FilePart` JSON object from a WebSocket message.
-   **Logic Flow**:
    1.  **Check for Inline Data**: The component first checks if `part.file.bytes` exists. If it does, the content is already available, and no network request is needed.
    2.  **Fetch from URI**: If `part.file.bytes` is null but `part.file.uri` exists, the component will:
        -   Display a loading state (e.g., a spinner or placeholder).
        -   Initiate an HTTP `fetch` call to the backend's `/api/v1/artifacts/download` endpoint, passing the URI.
        -   Handle the response, including potential errors (e.g., 403 Forbidden, 404 Not Found, 500 Server Error).
    3.  **Render by MIME Type**: Once the file content (as bytes or a Blob) is available, the component inspects `part.file.mime_type` and renders the appropriate view.

#### 4.2.2. Rendering Views

-   **Images (`image/*`)**: Create a local object URL from the blob (`URL.createObjectURL(blob)`) and render an `<img>` tag.
-   **Audio (`audio/*`)**: Create an object URL and render an `<audio>` tag with controls.
-   **Markdown (`text/markdown`)**: Decode the content to a string and use a frontend library (e.g., `react-markdown` or `marked`) to render it as HTML.
-   **CSV (`text/csv`)**: Decode the content and use a library (e.g., `papaparse`) to parse it into headers and rows. Render this data in a scrollable HTML `<table>`.
-   **JSON/YAML (`application/json`, `application/yaml`)**: Decode the content and use a syntax highlighting library (e.g., `Prism.js`, `highlight.js`) to display it within a scrollable `<pre><code>` block.
-   **Fallback (Default View)**: For any unhandled MIME type, or if a fetch fails, the component will render the standard file card. This card will include the filename, size, and a download icon. The download link will be an `<a>` tag pointing to the secure `/api/v1/artifacts/download` endpoint.

## 5. Security Considerations

-   The security of this feature hinges entirely on the robust implementation of authentication and authorization in the `/api/v1/artifacts/download` backend endpoint. This endpoint must never serve an artifact without confirming the current user has the right to access it.
-   The frontend should treat the download endpoint as the canonical source for file content and should not attempt to parse or access `artifact://` URIs directly.

## 6. Implementation Checklist

1.  [ ] **Backend**: Implement the secure `/api/v1/artifacts/download` endpoint in the gateway's web server.
    -   [ ] Add authentication middleware.
    -   [ ] Add authorization logic to validate the user against the artifact's context (`user_id`, `session_id`).
    -   [ ] Add logic to fetch and stream artifact bytes.
2.  [ ] **Frontend**: Refactor the file rendering component.
    -   [ ] Add logic to check for `bytes` vs. `uri`.
    -   [ ] Implement the on-demand `fetch` call with loading and error states.
    -   [ ] Implement the MIME type-based renderer `switch`.
    -   [ ] Create or integrate components for rendering tables (for CSV) and highlighted code (for JSON/YAML).
    -   [ ] Ensure the fallback file card includes a working download link to the new endpoint.
