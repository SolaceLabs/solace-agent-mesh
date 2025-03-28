# Approval Flow Feature

This document describes the approval flow feature, which allows agent actions to request approval from the originator before proceeding with certain operations.

## Overview

The approval flow feature enables agent actions to pause execution and request approval from the user (originator) before proceeding with sensitive or important operations. This is useful for scenarios where human oversight is required, such as:

- Deploying to production environments
- Creating or modifying user accounts
- Making purchases or financial transactions
- Executing potentially destructive operations
- Any action that requires human verification

## Architecture

The approval flow involves several components:

1. **Agent Action**: Initiates the approval request by returning an ActionResponse with an ApprovalRequest object
2. **Orchestrator**: Processes the approval request and forwards it to the AsyncService
3. **AsyncService**: Manages the state of paused tasks and handles timeouts
4. **Gateway**: Routes approval requests to the appropriate interface (e.g., Slack)
5. **Interface (e.g., Slack)**: Displays the approval form to the user and collects their response

## How to Use

### Creating an Action with Approval Request

To create an action that requires approval, you need to:

1. Import the necessary classes:
   ```python
   from ....common.action_response import ActionResponse, ApprovalRequest
   from ....common.form_utils import create_approval_form
   ```

2. Create an approval form schema and data:
   ```python
   # Create approval data
   approval_data = {
       "task_description": "Deploy to production",
       "requested_by": "user@example.com",
       "timestamp": "2023-01-01 12:00:00",
       # Add any other relevant data
   }

   # Create form schema
   form_schema = create_approval_form(
       approval_data=approval_data,
       title="Deployment Approval Request",
       description="Please review and approve this deployment request."
   )
   ```

3. Create an ApprovalRequest object:
   ```python
   approval_request = ApprovalRequest(
       form_schema=form_schema,
       approval_data=approval_data,
       approval_type="binary",  # binary (approve/reject)
       timeout_seconds=3600,  # 1 hour timeout
   )
   ```

4. Return an ActionResponse with the approval request:
   ```python
   return ActionResponse(
       message="Requesting approval for deployment to production",
       approval_request=approval_request,
   )
   ```

### Example Action

See the `ApprovalExampleAction` class in `src/agents/global/actions/approval_example_action.py` for a complete example.

### Form Utilities

The `form_utils` module provides utilities for creating and handling forms:

- `create_approval_form(approval_data, title, description)`: Creates an RJFS form schema from approval data
- `rjfs_to_slack_blocks(form_schema, approval_data)`: Converts an RJFS form schema to Slack blocks
- `extract_form_data_from_slack_payload(payload)`: Extracts form data from a Slack interaction payload

## Flow Sequence

1. User makes a request that triggers an action requiring approval
2. Action returns an ActionResponse with an ApprovalRequest
3. Orchestrator detects the approval request and forwards it to the AsyncService
4. AsyncService stores the task state and sends an approval request to the Gateway
5. Gateway forwards the approval request to the appropriate interface (e.g., Slack)
6. Interface displays the approval form to the user
7. User approves or rejects the request
8. Interface sends the response back to the Gateway
9. Gateway forwards the response to the AsyncService
10. AsyncService updates the task state and resumes the task if all approvals are received
11. Orchestrator restores the task state and continues processing

## Configuration

### AsyncService Configuration

The AsyncService can be configured in `configs/async_service.yaml`:

```yaml
async_service:
  db_config:
    type: ${ASYNC_DB_TYPE, "memory"}  # memory, mysql, postgres, sqlite
    host: ${ASYNC_DB_HOST, "localhost"}
    port: ${ASYNC_DB_PORT, 3306}
    username: ${ASYNC_DB_USERNAME, "root"}
    password: ${ASYNC_DB_PASSWORD, ""}
    database: ${ASYNC_DB_NAME, "async_service"}
  default_timeout_seconds: ${ASYNC_DEFAULT_TIMEOUT, 3600}
```

### Gateway Configuration

Add the approval flows to your gateway configuration by including `configs/gateway-approval-flows.yaml`.

## Error Handling

The approval flow handles several error scenarios:

1. **Timeout**: If the user doesn't respond within the timeout period, the AsyncService will mark the task as timed out and notify the user
2. **Database Failures**: If the database is unavailable, the system will fall back to in-memory storage
3. **Form Rendering Errors**: If there's an error rendering the form, a simplified form will be shown with just approve/reject buttons

## Security Considerations

- Only the originator of the request can approve it
- The system validates the identity of the user before processing approval responses

## Future Enhancements

Potential future enhancements include:

1. **Multiple Approvers**: Support for requiring approval from multiple users
2. **Custom Form Fields**: Allow actions to define custom form fields beyond simple approval/rejection
3. **Approval Delegation**: Allow users to delegate approval authority to others
4. **Approval History**: Track and display approval history for audit purposes
5. **Notification System**: Send reminders for pending approvals