# Feature Implementation Plan: User Feedback

**Objective:** To add a mechanism for users to provide "thumbs-up" or "thumbs-down" feedback on agent chat responses, with an option to add textual comments. This feature will be controlled by a backend configuration flag.

---

## Part 1: Backend Implementation

The backend will be responsible for providing the configuration to enable the feature, receiving the feedback via a new API endpoint, and processing it.

### Step 1: Create the Feedback Service

We will start by creating a new service to encapsulate the business logic for handling feedback. This keeps the API router clean and follows the existing architectural pattern.

*   **Action:** Create a new file: `src/solace_agent_mesh/gateway/http_sse/services/feedback_service.py`.
*   **Contents:**
    *   Define a `FeedbackService` class.
    *   The class will have an `async def process_feedback(self, payload: FeedbackPayload, user_id: str)` method.
    *   Initially, this method will simply log the received feedback payload to the console in a structured JSON format. This provides a simple but effective way to collect feedback without requiring immediate database changes.

### Step 2: Create the Feedback API Router

Next, we'll define the API endpoint that the frontend will call to submit feedback.

*   **Action:** Create a new file: `src/solace_agent_mesh/gateway/http_sse/routers/feedback.py`.
*   **Contents:**
    *   Define a FastAPI `APIRouter`.
    *   Define a Pydantic `FeedbackPayload` model to validate the incoming request body. It should include `messageId`, `sessionId`, `feedbackType` ('up' or 'down'), and an optional `feedbackText`.
    *   Create a `POST /api/v1/feedback` endpoint.
    *   This endpoint will depend on the `FeedbackService` (from Step 1) and the current `user_id` using the dependency injection system.
    *   It will call `feedback_service.process_feedback()` with the validated payload and user ID.

### Step 3: Integrate the New Service and Router

Now, we will wire the new service and router into the main application.

*   **File 1: `src/solace_agent_mesh/gateway/http_sse/component.py`**
    *   **Action:** Import `FeedbackService` and instantiate it within the `WebUIBackendComponent`.
    *   **Details:** In the `__init__` method, add `self.feedback_service = FeedbackService()`. Then, add a new getter method `get_feedback_service(self) -> FeedbackService` to expose the instance for dependency injection.

*   **File 2: `src/solace_agent_mesh/gateway/http_sse/dependencies.py`**
    *   **Action:** Create a dependency injector for the new service.
    *   **Details:** Import `FeedbackService`. Create a new function `get_feedback_service()` that depends on `get_sac_component` and returns `component.get_feedback_service()`.

*   **File 3: `src/solace_agent_mesh/gateway/http_sse/main.py`**
    *   **Action:** Mount the new API router.
    *   **Details:** Import the new `feedback` router from the `routers` package. In the `_setup_routers` function, add a line `app.include_router(feedback.router, prefix="/api/v1")` to make the endpoint live.

---

## Part 2: Frontend Implementation

The frontend will conditionally render the feedback UI based on the configuration flag and handle the user interaction.

### Step 4: Update Frontend Configuration

We need to ensure the frontend is aware of the new feature flag.

*   **File 1: `client/webui/frontend/src/lib/contexts/ConfigContext.ts`**
    *   **Action:** Add the `configCollectFeedback` property to the `ConfigContextValue` interface. This makes the flag accessible throughout the application via the React context.

*   **File 2: `client/webui/frontend/src/lib/providers/ConfigProvider.tsx`**
    *   **Action:** No changes are needed. The provider is already set up to fetch `frontend_collect_feedback` from the backend and map it to `configCollectFeedback`. We just need to ensure the backend `config` endpoint includes this flag in its response.

### Step 5: Implement the Feedback UI

This is the core of the frontend work, where we build the visual components for feedback.

*   **File: `client/webui/frontend/src/lib/components/chat/ChatMessage.tsx`**
    *   **Action:** Create a new internal React component named `FeedbackActions` and render it conditionally.
    *   **Details:**
        1.  The `FeedbackActions` component will use the `useChatContext` hook to get the `configCollectFeedback` flag. If the flag is `false`, it will render nothing.
        2.  It will use `useState` to manage its internal state: `idle` (showing thumbs), `prompting` (showing text area), and `submitted` (showing a "thank you" message).
        3.  In the `idle` state, it will render `ThumbsUp` and `ThumbsDown` icons (from `lucide-react`) inside the `ChatBubbleActionWrapper`.
        4.  Clicking a thumb icon will change the state to `prompting` and record whether it was an "up" or "down" vote.
        5.  In the `prompting` state, it will render a `Textarea` and a "Submit" `Button`.
        6.  When the "Submit" button is clicked, it will call a new API function (see Step 6) and change its state to `submitted`.
    *   **Integration:** In the `getChatBubble` function within `ChatMessage.tsx`, conditionally render the new `FeedbackActions` component for completed agent messages (i.e., when `!message.isUser && message.isComplete`).

### Step 6: Create the Feedback API Client Function

Finally, we'll create the function responsible for sending the feedback data to the backend.

*   **File: `client/webui/frontend/src/lib/utils/api.ts`**
    *   **Action:** Create a new exported async function named `submitFeedback`.
    *   **Details:**
        1.  The function will take a `FeedbackPayload` object as an argument, which includes `messageId`, `sessionId`, `feedbackType`, and `feedbackText`.
        2.  It will use the existing `authenticatedFetch` helper to make a `POST` request to `/api/v1/feedback`.
        3.  It will serialize the payload into a JSON body for the request.
