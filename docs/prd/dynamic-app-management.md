# PRD: Dynamic App Management Control Plane

**Jira:** [DATAGO-125498](https://sol-jira.atlassian.net/browse/DATAGO-125498)
**Parent Epic:** [DATAGO-122424](https://sol-jira.atlassian.net/browse/DATAGO-122424)
**Status:** Draft

## 1. Problem Statement

SAC (Solace AI Connector) is the runtime for SAM (Solace Agent Mesh). It supports running many apps concurrently - agents, gateways, workflows, and services - but requires a full process restart to create or remove any app. This prevents runtime deployment of new agents, dynamic scaling, configuration updates, and graceful decommissioning of individual apps.

As SAM moves toward enterprise deployment scenarios (multi-tenant environments, dynamic agent provisioning, app studio tooling), the inability to manage apps at runtime is a blocking limitation.

## 2. Goals

1. Enable creating, stopping, starting, updating, and removing individual SAC apps at runtime without affecting other running apps
2. Expose this capability through a RESTful API over the Solace broker, making it accessible to any component in the mesh
3. Provide RBAC-controlled access to app management operations
4. Support custom per-app management endpoints so different app types (agents, gateways, workflows) can expose type-specific operations
5. Maintain full backwards compatibility - all changes to SAC are additive

## 3. Non-Goals

- Dynamic configuration changes while an app is actively processing (stop/reconfig/start is acceptable)
- Connection sharing between apps/components (existing limitation, separate concern)
- UI for app management (this is the API layer; UI is a separate effort)
- Hot-reload of Python code without stop/start

## 4. User Stories

### 4.1 Platform Operator
> As a platform operator, I want to deploy a new agent to a running SAM instance without restarting, so that I can add capabilities without downtime.

### 4.2 Platform Operator
> As a platform operator, I want to stop and remove an agent that is no longer needed, so that I can free resources without affecting other agents.

### 4.3 Platform Operator
> As a platform operator, I want to update an agent's configuration (model, instructions, tools) and restart it, so that I can iterate on agent behavior without full system restart.

### 4.4 Platform Operator
> As a platform operator, I want to view the status of all running apps, so that I can monitor the health of the system.

### 4.5 Enterprise Admin
> As an enterprise admin, I want app management operations to be protected by RBAC, so that only authorized users can create, modify, or remove apps.

### 4.6 Agent Developer
> As an agent developer, I want my agent type to expose custom management endpoints (e.g., list tools, view sessions), so that operators can inspect agent-specific state.

## 5. Architecture Overview

### 5.1 Three-Layer Design

```
                    +-----------------------+
                    |  SAM Enterprise       |
                    |  (RBAC / Auth)        |
                    +-----------+-----------+
                                |
                    +-----------v-----------+
                    |  SAM Core             |
                    |  Controller Service   |
                    |  (broker subscriber,  |
                    |   request routing,    |
                    |   RBAC hooks)         |
                    +-----------+-----------+
                                |
                    +-----------v-----------+
                    |  SAC                  |
                    |  (App lifecycle,      |
                    |   add/remove/stop/    |
                    |   start, get_info)    |
                    +-----------------------+
```

**SAC** provides the primitive operations (stop, start, add, remove) on apps.
**SAM** provides the controller service that exposes these as a RESTful API over the broker.
**Enterprise** provides RBAC authorization for control operations.

### 5.2 Communication Pattern

The control plane uses Solace pub/sub messaging with JSON-RPC format:

1. A requester publishes a request to a control topic
2. The controller service (subscribed to `{ns}/sam/v1/control/>`) receives it
3. Controller authorizes the request, executes the operation
4. Controller publishes the response to the requester's reply-to topic

This is fully asynchronous - no blocking. The response is published when the operation completes, even if that takes significant time (e.g., waiting for in-flight messages to drain during a stop).

## 6. Functional Requirements

### 6.1 SAC: Per-App Lifecycle Management

**FR-1:** Each app MUST have an independent stop mechanism that does not affect other running apps.

**FR-2:** `App.stop(timeout)` MUST:
- Signal all the app's component threads to stop accepting new messages
- Wait for in-flight messages to complete processing
- Disconnect broker connections
- Accept an optional timeout parameter; if exceeded, force-stop remaining threads

**FR-3:** `App.start()` MUST be callable after `stop()` to restart the app with its current configuration.

**FR-4:** Each app MUST expose `enabled` (desired state: boolean) and `status` (observed state: string) properties.

**FR-5:** Status values: `created`, `starting`, `running`, `stopping`, `stopped`, `error`.

**FR-6:** `App.get_info()` MUST return a dict with at minimum: `name`, `enabled`, `status`, `num_instances`.

**FR-7:** `App.get_management_endpoints()` and `App.handle_management_request()` MUST be available as override points for subclasses. Default implementations return empty list and None respectively.

### 6.2 SAC: Runtime App Addition/Removal

**FR-8:** `SolaceAiConnector.add_app(app_info)` MUST create, register, and run an app at runtime using the same pipeline as startup (supporting `app_module`, custom App subclasses, etc.).

**FR-9:** `SolaceAiConnector.remove_app(app_name, timeout)` MUST stop the app (waiting for in-flight work), deregister it from all tracking structures, and clean up resources.

**FR-10:** All mutations to the apps list, flows list, and flow_input_queues MUST be thread-safe.

**FR-11:** App names MUST be unique. `add_app()` MUST reject duplicate names.

### 6.3 SAC: Backwards Compatibility

**FR-12:** All changes MUST be additive. Existing apps that don't use new features MUST continue to work identically.

**FR-13:** The existing connector-level `stop()` MUST continue to stop all apps as it does today.

**FR-14:** Existing config files MUST work without modification.

### 6.4 SAM: Controller Service

**FR-15:** The controller MUST be a SAM app (SamAppBase subclass) configured via YAML like any other SAM service.

**FR-16:** The controller MUST subscribe to `{ns}/sam/v1/control/>` to receive all control requests.

**FR-17:** The controller MUST support the following RESTful operations:

| Resource | Method | Description |
|----------|--------|-------------|
| `/apps` | GET | List all apps with basic info |
| `/apps` | POST | Create and start a new app |
| `/apps/{name}` | GET | Get detailed info for a specific app |
| `/apps/{name}` | PUT | Replace app config (stop/reconfig/start) |
| `/apps/{name}` | PATCH | Partial update (e.g., `{"enabled": false}` to stop) |
| `/apps/{name}` | DELETE | Remove an app |
| `/apps/{name}/{path}` | any | Delegate to app's custom management handler |

**FR-18:** Requests MUST use JSON-RPC 2.0 format:
```json
{
    "jsonrpc": "2.0",
    "id": "<correlation-id>",
    "method": "<GET|POST|PUT|PATCH|DELETE>",
    "params": { "body": { ... } }
}
```

**FR-19:** Responses MUST use JSON-RPC 2.0 format with `result` (success) or `error` (failure).

**FR-20:** The controller MUST have a middleware hook for authorization. In SAM core, the default authorization behavior is configurable (e.g., `none` for dev). Enterprise overrides this.

### 6.5 SAM: Scopes and Authorization

**FR-21:** Control plane operations MUST map to scopes following the existing 3-part pattern:

```
sam:apps:read      - GET operations
sam:apps:create    - POST (create new app)
sam:apps:update    - PUT/PATCH (modify existing app)
sam:apps:delete    - DELETE (remove app)
sam:apps/*:manage  - Custom app endpoint access (wildcard)
sam:apps/{name}:manage - Per-app custom endpoint access
```

**FR-22:** Enterprise MUST be able to define roles with control plane scopes using existing role-to-scope definition YAML.

**FR-23:** User identity for RBAC MUST be extracted from the message using the existing Trust Manager JWT pattern (gateway signs identity, controller verifies).

### 6.6 Custom App Management Endpoints

**FR-24:** Any App subclass MAY override `get_management_endpoints()` to advertise custom endpoints and `handle_management_request()` to handle them.

**FR-25:** The controller MUST route requests with paths beyond `/apps/{name}` to the target app's `handle_management_request()` method.

**FR-26:** Custom endpoint requests MUST be authorized using the `sam:apps/{name}:manage` scope.

## 7. API Specification

### 7.1 Topic Structure

```
{namespace}/sam/v1/control/apps                          # Collection
{namespace}/sam/v1/control/apps/{app_name}               # Individual app
{namespace}/sam/v1/control/apps/{app_name}/{custom_path}  # Custom endpoints
```

### 7.2 List Apps

**Topic:** `{ns}/sam/v1/control/apps`
**Method:** GET
**Scope:** `sam:apps:read`

**Response:**
```json
{
    "jsonrpc": "2.0",
    "id": "req-1",
    "result": {
        "apps": [
            {
                "name": "my_agent_app",
                "enabled": true,
                "status": "running",
                "num_instances": 1,
                "app_module": "solace_agent_mesh.agent.sac.app"
            }
        ]
    }
}
```

### 7.3 Create App

**Topic:** `{ns}/sam/v1/control/apps`
**Method:** POST
**Scope:** `sam:apps:create`

**Request body:** Full app config (same structure as YAML `apps[]` entry)
```json
{
    "name": "new_agent",
    "app_module": "solace_agent_mesh.agent.sac.app",
    "broker": { ... },
    "app_config": { ... }
}
```

**Response:** The created app's `get_info()` result.

### 7.4 Get App

**Topic:** `{ns}/sam/v1/control/apps/{name}`
**Method:** GET
**Scope:** `sam:apps:read`

**Response:** App's `get_info()` result plus any additional metadata from custom app types.

### 7.5 Update App (Full Replace)

**Topic:** `{ns}/sam/v1/control/apps/{name}`
**Method:** PUT
**Scope:** `sam:apps:update`

**Request body:** Full new app config.

**Behavior:** Stop app (if running) -> Apply new config -> Start app (if previously enabled).

### 7.6 Patch App (Partial Update)

**Topic:** `{ns}/sam/v1/control/apps/{name}`
**Method:** PATCH
**Scope:** `sam:apps:update`

**Request body examples:**
```json
{"enabled": false}   // Stop the app
{"enabled": true}    // Start the app
{"num_instances": 3} // Scale (triggers stop/reconfig/start)
```

### 7.7 Delete App

**Topic:** `{ns}/sam/v1/control/apps/{name}`
**Method:** DELETE
**Scope:** `sam:apps:delete`

**Behavior:** Stop app (if running) -> Deregister -> Cleanup.

### 7.8 Custom App Endpoint

**Topic:** `{ns}/sam/v1/control/apps/{name}/{custom_path}`
**Method:** any
**Scope:** `sam:apps/{name}:manage`

**Behavior:** Delegated to `app.handle_management_request(method, path_parts, body, context)`.

### 7.9 Error Responses

```json
{
    "jsonrpc": "2.0",
    "id": "req-1",
    "error": {
        "code": -32001,
        "message": "App 'xyz' not found"
    }
}
```

Error codes:
- `-32600` - Invalid request (malformed JSON-RPC)
- `-32601` - Method not allowed
- `-32001` - Resource not found
- `-32002` - Conflict (e.g., duplicate app name)
- `-32003` - Authorization denied
- `-32004` - Operation failed (e.g., stop timeout)

## 8. Non-Functional Requirements

**NFR-1:** Stopping an app MUST NOT cause message loss. In-flight messages MUST complete processing before the app is fully stopped.

**NFR-2:** Adding or removing an app MUST NOT disrupt other running apps. No message loss, no reconnections, no service interruption for unrelated apps.

**NFR-3:** The control plane MUST work with both real Solace brokers and DevBroker (dev mode).

**NFR-4:** All SAC changes MUST be backwards compatible. No existing tests should break. No existing config files should require changes.

**NFR-5:** The controller service MUST handle concurrent control requests safely.

**NFR-6:** App configs are held in memory only from SAC's perspective. Persistence is the responsibility of the Platform Service (database).

## 9. Security Considerations

- Control plane messages are exchanged over the broker, inheriting the broker's transport security (TLS)
- RBAC is enforced at the SAM controller layer, not in SAC (SAC has no concept of users/auth)
- User identity is propagated via signed JWT in the message (existing Trust Manager pattern)
- In dev mode without Enterprise, authorization can be configured as `none` (all operations allowed) or `deny_all`
- The controller MUST NOT expose sensitive configuration data (passwords, keys) in `get_info()` responses

## 10. Configuration

### Controller Service YAML

```yaml
- name: sam_control_service
  app_module: solace_agent_mesh.services.control.app
  broker:
    <<: *broker_connection
  app_config:
    namespace: ${NAMESPACE}
    authorization:
      type: none  # "none", "deny_all", or Enterprise overrides to "default_rbac"
```

## 11. Success Criteria

1. A new agent can be deployed to a running SAM instance via a broker message, and it begins processing requests
2. An existing agent can be stopped without affecting other agents, with all in-flight work completed
3. An agent can be removed from the system entirely via a broker message
4. All operations are authorized through RBAC when Enterprise is present
5. Existing SAM deployments work identically with no config changes required
6. All three repos have passing test suites

## 12. Repos and Branching

| Repo | Branch | Scope |
|------|--------|-------|
| `solace-ai-connector` | `ed/DATAGO-125498/dynamic-app-management` | Per-app lifecycle, add/remove, thread safety |
| `solace-agent-mesh` | `ed/DATAGO-125498/dynamic-app-management` | Controller service, operations, RBAC hooks |
| `solace-agent-mesh-enterprise` | `ed/DATAGO-125498/dynamic-app-management` | Scope definitions, RBAC integration |

Implementation order: SAC -> SAM -> Enterprise (each phase independently testable).

## 13. Open Questions

1. Should the controller service be automatically included in every SAM deployment, or require explicit configuration? (Current decision: explicit config, future work to simplify)
2. Should there be a maximum timeout for `stop()` beyond which it force-kills threads? What is a reasonable default?
3. For the PUT (full update) operation, should the controller validate that the new config is structurally valid before stopping the old app?
