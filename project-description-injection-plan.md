# Project Description Injection Implementation Plan

## Overview
Implement project description injection into user's first message when a project is active, following the same pattern as `_inject_gateway_instructions_callback` but at the gateway preprocessing stage.

## File to Modify
`/src/solace_agent_mesh/gateway/http_sse/routers/tasks.py`

## Step 1: Add Project Service Import
**Location**: Top of file, around line 28-32 (with other dependencies)
```python
from ....gateway.http_sse.infrastructure.dependency_injection import get_project_service
from ....gateway.http_sse.application.services.project_service import ProjectService
```

## Step 2: Add Project Service Dependency
**Location**: Function signature of `_submit_task` (around line 42)
```python
async def _submit_task(
    request: FastAPIRequest,
    payload: Union[SendMessageRequest, SendStreamingMessageRequest],
    session_manager: SessionManager,
    component: "WebUIBackendComponent",
    project_service: ProjectService = Depends(get_project_service),  # ADD THIS
    is_streaming: bool,
):
```

## Step 3: Add Project Description Injection Logic
**Location**: After line 146 (after message text extraction), before line 169 (before A2A processing)

```python
# Project description injection for first message in session
if project_id and message_text and is_streaming:
    try:
        user_id = user_identity.get("id")
        
        # Check if this is the first message in the session
        if hasattr(component, "persistence_service") and component.persistence_service:
            from ....gateway.http_sse.dependencies import get_session_service
            session_service = get_session_service(component)
            
            # Get message history to determine if this is the first message
            history = session_service.get_session_history(session_id=session_id, user_id=user_id)
            if not history or history.total_message_count == 0:  # First message
                # Fetch project description
                project = project_service.get_project(project_id, user_id)
                if project and project.description and project.description.strip():
                    project_context = f"Project Context: {project.description.strip()}\n\n"
                    message_text = project_context + message_text
                    log.info("%sInjected project description for project: %s", log_prefix, project_id)
    except Exception as e:
        log.warning("%sFailed to inject project description: %s", log_prefix, e)
        # Continue without injection - don't fail the request
```

## Step 4: Update Function Calls
**Location**: Lines 233 and 254 (where `_submit_task` is called)

**In `send_task_to_agent`**:
```python
return await _submit_task(
    request=request,
    payload=payload,
    session_manager=session_manager,
    component=component,
    project_service=project_service,  # ADD THIS
    is_streaming=False,
)
```

**In `subscribe_task_from_agent`**:
```python
return await _submit_task(
    request=request,
    payload=payload,
    session_manager=session_manager,
    component=component,
    project_service=project_service,  # ADD THIS
    is_streaming=True,
)
```

## Step 5: Add Project Service Parameter to Route Handlers
**Location**: Function signatures at lines 223 and 243

```python
@router.post("/message:send", response_model=SendMessageSuccessResponse)
async def send_task_to_agent(
    request: FastAPIRequest,
    payload: SendMessageRequest,
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService = Depends(get_project_service),  # ADD THIS
):

@router.post("/message:stream", response_model=SendStreamingMessageSuccessResponse)
async def subscribe_task_from_agent(
    request: FastAPIRequest,
    payload: SendStreamingMessageRequest,
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService = Depends(get_project_service),  # ADD THIS
):
```

## Implementation Details

### Injection Conditions:
1. `project_id` exists in message metadata
2. `message_text` is not empty
3. `is_streaming` is True (only for streaming messages)
4. This is the first message in the session
5. Project has a description

### Message Format:
```
Project Context: [Project Description]

[Original User Message]
```

### Error Handling:
- Graceful fallback if project service fails
- Continue without injection rather than failing the request
- Log warnings for debugging

### Performance Considerations:
- Only runs on first message per session
- Database calls are minimal (one project lookup)
- Existing session service calls are reused

## Testing Scenarios
1. First message with project description → Should inject
2. Subsequent messages → Should not inject
3. No project selected → Should not inject
4. Project without description → Should not inject
5. Database/service errors → Should gracefully continue

## Pattern Comparison
This implementation follows the same pattern as `_inject_gateway_instructions_callback` in `/src/solace_agent_mesh/agent/sac/component.py:1111`, but at the gateway preprocessing stage rather than the agent callback stage.

### Benefits of Gateway-side Injection:
1. **User context**: Project description becomes part of the conversation history
2. **Visibility**: User can see the injected content in chat
3. **Persistence**: Gets stored in message history
4. **Simplicity**: No agent configuration needed

This implementation is lightweight, robust, and follows existing codebase patterns.
