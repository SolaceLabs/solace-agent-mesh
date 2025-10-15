# SAM Trust Manager - Phase 1 Detailed Design Document

## Overview

This document describes the detailed design for Phase 1 of the SAM Trust Manager implementation in the **solace-agent-mesh-enterprise** repository. This phase focuses on creating, publishing, receiving, and storing Trust Cards, establishing the infrastructure for component identity verification.

**Repository Context**: This implementation is part of the enterprise repository (`solace-agent-mesh-enterprise`). The open source repository (`solace-agent-mesh`) provides integration hooks that this enterprise implementation uses.

**Phase 1 Scope**: Trust Card infrastructure only
- Key pair generation and management
- Trust Card creation with JWKS
- Periodic Trust Card publishing
- Trust Card reception and verification
- Trust Registry for storing component public keys

**Out of Scope for Phase 1**:
- JWT signing of user identity claims
- JWT verification
- Signature validation beyond basic format checks
- Trust Card self-signatures (structure prepared, validation deferred to Phase 2)

---

## Architecture Overview

### Design Principles

1. **Minimal Invasiveness**: Integration into existing components requires minimal changes to existing code
2. **Optional Feature**: Trust Manager can be enabled/disabled via configuration
3. **Consistent Patterns**: Follow existing SAM patterns (similar to IdentityService, AgentRegistry)
4. **Thread Safety**: All registry operations must be thread-safe
5. **Async-First**: Key operations (card publishing, verification) are async
6. **ACL-Based Trust**: Topic structure enforced by broker ACLs is the root of trust
7. **Standards Compliance**: Use JWKS (RFC 7517) for key distribution

### Component Interaction Flow

```
Component Startup
    ├─> Load Configuration
    ├─> Initialize TrustManager (if enabled)
    │   ├─> KeyManager.load_or_generate_keys()
    │   ├─> Create TrustCard with JWKS
    │   └─> Schedule periodic publishing
    ├─> Subscribe to trust card topics
    └─> Start normal operations

Trust Card Publishing (Periodic)
    ├─> TrustManager.publish_trust_card()
    ├─> Create TrustCard with current JWKS
    ├─> Publish to {namespace}/a2a/v1/trust/{component-type}/{component-id}
    └─> Log publication

Trust Card Reception
    ├─> Message arrives on trust topic
    ├─> Extract component_type and component_id from topic
    ├─> Parse TrustCard from payload
    ├─> TrustManager.handle_trust_card()
    │   ├─> Verify topic matches payload
    │   ├─> Validate JWKS format
    │   ├─> Check expiration
    │   └─> TrustRegistry.add_or_update()
    └─> Store with topic-derived metadata
```

---

## New Files to Create (Enterprise Repository)

All files are created in the `solace-agent-mesh-enterprise` repository.

### 1. `src/solace_agent_mesh_enterprise/common/trust/__init__.py`

**Purpose**: Package initializer for the trust module

**Exports**:
```python
from .trust_manager import TrustManager
from .trust_card import TrustCard
from .trust_registry import TrustRegistry
from .key_manager import KeyManager
from .exceptions import (
    TrustError,
    KeyGenerationError,
    CardVerificationError,
    InvalidCardError,
)

# Factory function for open source integration
def initialize_trust_manager(component):
    """
    Factory function called by open source components to initialize Trust Manager.
    
    Args:
        component: SamComponentBase instance from open source
        
    Returns:
        TrustManager instance or None if not enabled
    """
    trust_config = component.get_config("trust_manager")
    if not trust_config or not trust_config.get("enabled", False):
        return None
    
    return TrustManager(
        component_id=component._get_component_id(),
        component_type=component._get_component_type(),
        namespace=component.namespace,
        config=trust_config,
        publish_callback=component.publish_a2a_message,
        log_identifier=component.log_identifier
    )
```

**Content**: Standard Python package init with imports from submodules and factory function for open source integration

---

### 2. `src/solace_agent_mesh_enterprise/common/trust/trust_card.py`

**Purpose**: Pydantic model for Trust Cards

**Dependencies**:
- `pydantic` - For model validation
- `typing` - For type hints
- `datetime` - For timestamp handling

**Key Classes**:

#### `TrustCard(BaseModel)`
Represents a component's trust credentials.

**Fields**:
- `component_type: str` - Type of component ("gateway", "agent", etc.)
- `component_id: str` - Unique identifier (must match client-username)
- `namespace: str` - SAM namespace
- `jwks: Dict[str, Any]` - JSON Web Key Set containing public keys
- `issued_at: int` - Unix epoch milliseconds when card was created
- `expires_at: int` - Unix epoch milliseconds when card expires
- `version: str = "1.0"` - Trust Card format version

**Methods**:
- `model_dump()` - Serialize to dict (inherited from BaseModel)
- `model_validate()` - Deserialize from dict (class method, inherited)
- `is_expired() -> bool` - Check if card has expired based on current time
- `get_public_keys() -> List[Dict[str, Any]]` - Extract keys array from JWKS
- `get_key_by_id(kid: str) -> Optional[Dict[str, Any]]` - Find specific key in JWKS

**Validators**:
- `@field_validator("component_type")` - Must be non-empty string
- `@field_validator("component_id")` - Must be non-empty string
- `@field_validator("namespace")` - Must be non-empty string
- `@field_validator("jwks")` - Must contain "keys" array with at least one key
- `@model_validator(mode="after")` - Verify issued_at <= expires_at

**Design Notes**:
- Follows same pattern as `AgentCard` in existing codebase
- Uses Pydantic v2 validation patterns
- JWKS format follows RFC 7517
- Timestamps in milliseconds for consistency with existing SAM code
- No signature field in Phase 1 (structure prepared for Phase 2)

---

### 3. `src/solace_agent_mesh_enterprise/common/trust/trust_registry.py`

**Purpose**: Thread-safe storage for discovered Trust Cards

**Dependencies**:
- `threading` - For Lock
- `typing` - For type hints
- `logging` - For operation logging
- `.trust_card` - For TrustCard model

**Key Classes**:

#### `TrustRegistry`
Stores and manages Trust Cards from other components.

**Internal State**:
- `_trust_cards: Dict[str, TrustCard]` - Maps component_id to TrustCard
- `_lock: threading.Lock` - Thread safety for all operations
- `_log_identifier: str` - For consistent logging

**Methods**:

##### `__init__(log_identifier: str = "[TrustRegistry]")`
- Initializes empty registry
- Creates thread lock
- Sets up logging identifier

##### `add_or_update(component_id: str, trust_card: TrustCard) -> bool`
- Adds new or updates existing trust card
- Returns True if new card, False if update
- Thread-safe operation (uses lock)
- Logs addition/update at INFO level
- Validates component_id matches trust_card.component_id

##### `get_trust_card(component_id: str) -> Optional[TrustCard]`
- Retrieves trust card by component ID
- Returns None if not found
- Thread-safe operation (uses lock)
- Returns copy to prevent external modification

##### `get_component_type(component_id: str) -> Optional[str]`
- Gets component type for a component ID
- Returns None if component not found
- Used for authorization checks (e.g., "is this a gateway?")
- Thread-safe operation

##### `get_jwks(component_id: str) -> Optional[Dict[str, Any]]`
- Gets JWKS for a component
- Returns None if component not found
- Used for JWT verification (Phase 2)
- Thread-safe operation
- Returns copy to prevent modification

##### `list_components() -> List[str]`
- Returns sorted list of all component IDs
- Thread-safe operation
- Useful for debugging and monitoring

##### `remove_expired() -> int`
- Removes all expired trust cards
- Returns count of removed cards
- Should be called periodically
- Thread-safe operation
- Logs each removal at INFO level

##### `clear()`
- Removes all trust cards
- Used for testing/cleanup
- Thread-safe operation

**Design Notes**:
- Similar pattern to `AgentRegistry`
- All public methods are thread-safe
- No persistence in Phase 1 (cards rebuilt on restart)
- Component type stored from topic, not payload (security critical)
- Returns copies of mutable objects to prevent external modification

---

### 4. `src/solace_agent_mesh_enterprise/common/trust/key_manager.py`

**Purpose**: Manages ECDSA key pair generation, loading, and storage

**Dependencies**:
- `cryptography.hazmat.primitives.asymmetric.ec` - For ECDSA key operations
- `cryptography.hazmat.primitives.serialization` - For key serialization
- `cryptography.hazmat.backends` - For cryptography backend
- `pathlib` - For file path handling
- `logging` - For operation logging
- `typing` - For type hints
- `base64` - For encoding key coordinates
- `os` - For file operations

**Key Classes**:

#### `KeyManager`
Handles cryptographic key operations for Trust Manager.

**Configuration Parameters**:
- `key_storage_type: str` - "file", "env", or "memory"
- `private_key_path: Optional[str]` - Path for file storage (required if type="file")
- `component_id: str` - Used for key identification
- `log_identifier: str` - For consistent logging

**Internal State**:
- `_private_key: Optional[ec.EllipticCurvePrivateKey]` - ECDSA private key (P-256 curve)
- `_public_key: Optional[ec.EllipticCurvePublicKey]` - ECDSA public key
- `_key_id: str` - Unique identifier for current key (format: "{component_id}-key-{timestamp}")
- `_config: Dict[str, Any]` - Storage configuration

**Methods**:

##### `__init__(config: Dict[str, Any], component_id: str, log_identifier: str)`
- Validates configuration
- Stores component_id for key identification
- Does not generate keys (call load_or_generate_keys)

##### `async load_or_generate_keys() -> None`
- Attempts to load existing key based on storage type
- If load fails or no key exists, generates new key pair
- Saves new key if storage type supports it
- Generates unique key_id
- Logs all operations at INFO level
- Raises KeyGenerationError on failure

##### `get_private_key() -> ec.EllipticCurvePrivateKey`
- Returns private key
- Raises TrustError if keys not initialized
- Used for signing operations (Phase 2)

##### `get_public_key() -> ec.EllipticCurvePublicKey`
- Returns public key
- Raises TrustError if keys not initialized
- Used for JWKS generation

##### `get_key_id() -> str`
- Returns current key ID
- Used in JWKS and JWT headers

##### `generate_jwks() -> Dict[str, Any]`
- Creates JWKS structure from current public key
- Returns dict conforming to RFC 7517
- Includes single key with:
  - `kty: "EC"` - Key type
  - `crv: "P-256"` - Curve name
  - `x: str` - Base64url-encoded X coordinate
  - `y: str` - Base64url-encoded Y coordinate
  - `use: "sig"` - Key usage
  - `kid: str` - Key ID from get_key_id()
  - `alg: "ES256"` - Algorithm

##### `_generate_new_key_pair() -> None`
- Generates new ECDSA key pair using P-256 curve
- Updates _private_key, _public_key, and _key_id
- Private method

##### `_load_key_from_file() -> bool`
- Loads private key from file path
- Returns True if successful, False if file doesn't exist
- Raises KeyGenerationError on invalid key format
- Private method

##### `_save_key_to_file() -> None`
- Saves private key to file path in PEM format
- Creates parent directories if needed
- Sets restrictive file permissions (0o600)
- Private method

##### `_load_key_from_env() -> bool`
- Loads private key from environment variable
- Environment variable name: `SAM_TRUST_KEY_{component_id.upper()}`
- Returns True if successful, False if env var not set
- Private method

**Design Notes**:
- Uses ECDSA with P-256 curve (ES256) for compatibility with JWT standards
- File storage uses PEM format for interoperability
- Memory storage means keys regenerated on each restart
- Environment variable storage useful for containerized deployments
- Key rotation support deferred to future enhancement
- All file operations are async-compatible
- Private key never exposed in logs

---

### 5. `src/solace_agent_mesh_enterprise/common/trust/trust_manager.py`

**Purpose**: Main orchestrator for Trust Manager functionality

**Dependencies**:
- `logging` - For operation logging
- `typing` - For type hints
- `asyncio` - For async operations
- `.trust_card` - For TrustCard model
- `.trust_registry` - For TrustRegistry
- `.key_manager` - For KeyManager
- `.exceptions` - For custom exceptions
- `solace_agent_mesh.common.a2a.protocol` - For topic construction (from open source)
- `datetime` - For timestamp generation

**Key Classes**:

#### `TrustManager`
Orchestrates all trust-related operations for a component.

**Configuration Parameters**:
- `component_id: str` - Unique component identifier
- `component_type: str` - Type of component ("gateway", "agent")
- `namespace: str` - SAM namespace
- `config: Dict[str, Any]` - Trust manager configuration block
- `publish_callback: Callable[[Dict, str], None]` - Function to publish messages
- `log_identifier: str` - For consistent logging

**Internal State**:
- `_key_manager: KeyManager` - Manages cryptographic keys
- `_trust_registry: TrustRegistry` - Stores other components' trust cards
- `_component_id: str` - This component's ID
- `_component_type: str` - This component's type
- `_namespace: str` - SAM namespace
- `_publish_callback: Callable` - Function to publish to broker
- `_config: Dict[str, Any]` - Configuration
- `_log_identifier: str` - Logging prefix

**Methods**:

##### `__init__(component_id, component_type, namespace, config, publish_callback, log_identifier)`
- Validates required parameters
- Creates KeyManager instance
- Creates TrustRegistry instance
- Stores configuration
- Does not initialize keys (call initialize())

##### `async initialize() -> None`
- Calls key_manager.load_or_generate_keys()
- Publishes initial trust card
- Logs successful initialization
- Should be called during component async setup

##### `async publish_trust_card() -> None`
- Creates TrustCard with current JWKS
- Sets issued_at to current time
- Sets expires_at based on config (default: 30 days)
- Constructs topic: {namespace}/a2a/v1/trust/{component_type}/{component_id}
- Calls publish_callback with card payload and topic
- Logs publication at INFO level
- Handles exceptions gracefully (logs error, doesn't raise)

##### `async handle_trust_card(message_payload: Dict[str, Any], topic: str) -> bool`
- Extracts component_type and component_id from topic
- Parses TrustCard from payload
- Validates topic matches payload (security critical):
  - topic component_type must match payload component_type
  - topic component_id must match payload component_id
- Validates JWKS format
- Checks card expiration
- Stores in registry with topic-derived metadata
- Returns True if successful, False otherwise
- Logs all validation failures at WARNING level
- Logs successful storage at INFO level

##### `get_trust_registry() -> TrustRegistry`
- Returns reference to trust registry
- Used by other components for verification (Phase 2)

##### `get_component_identity() -> Dict[str, str]`
- Returns dict with component_id, component_type, namespace
- Useful for debugging and monitoring

**Helper Methods**:

##### `_create_trust_card() -> TrustCard`
- Creates TrustCard instance with current state
- Gets JWKS from key_manager
- Sets timestamps
- Private method

##### `_extract_component_info_from_topic(topic: str) -> Tuple[str, str]`
- Parses topic to extract component_type and component_id
- Returns (component_type,  component_id)
- Raises ValueError if topic format invalid
- Private method

##### `_validate_jwks_format(jwks: Dict[str, Any]) -> bool`
- Validates JWKS structure
- Checks for required fields
- Returns True if valid, False otherwise
- Private method

**Design Notes**:
- Async-first design for all I/O operations
- Publish callback pattern allows testing without broker
- All validation errors logged but don't crash component
- Topic parsing is security-critical (ACL enforcement point)
- Registry access provided for Phase 2 JWT verification
- No signature verification in Phase 1 (structure prepared)

---

### 6. `src/solace_agent_mesh_enterprise/common/trust/exceptions.py`

**Purpose**: Custom exceptions for Trust Manager

**Exception Hierarchy**:

```
TrustError (base)
├── KeyGenerationError
├── CardVerificationError
├── InvalidCardError
└── ConfigurationError
```

**Exception Classes**:

#### `TrustError(Exception)`
- Base exception for all trust-related errors
- Includes message and optional data dict

#### `KeyGenerationError(TrustError)`
- Raised when key generation or loading fails
- Includes details about failure reason

#### `CardVerificationError(TrustError)`
- Raised when trust card verification fails
- Includes details about what validation failed

#### `InvalidCardError(TrustError)`
- Raised when trust card format is invalid
- Includes details about format issues

#### `ConfigurationError(TrustError)`
- Raised when trust manager configuration is invalid
- Includes details about configuration problem

**Design Notes**:
- Follows Python exception best practices
- All exceptions include descriptive messages
- Optional data dict for structured error information
- Consistent with existing SAM exception patterns

---

## Modifications to Existing Files

### 1. `src/solace_agent_mesh/common/a2a/protocol.py`

**Changes Required**:

#### Add Trust Card Topic Functions

**New Functions to Add**:

##### `get_trust_card_topic(namespace: str, component_type: str, component_id: str) -> str`
- Returns topic for publishing a trust card
- Format: `{namespace}/a2a/v1/trust/{component_type}/{component_id}`
- Validates all parameters are non-empty
- Raises ValueError if validation fails

##### `get_trust_card_subscription_topic(namespace: str, component_type: Optional[str] = None) -> str`
- Returns subscription pattern for trust cards
- If component_type provided: `{namespace}/a2a/v1/trust/{component_type}/*`
- If component_type is None: `{namespace}/a2a/v1/trust/*/*`
- Allows subscribing to all trust cards or specific component type

##### `extract_trust_card_info_from_topic(topic: str) -> Tuple[str, str]`
- Extracts component_type and component_id from trust card topic
- Returns (component_type, component_id)
- Validates topic format matches expected pattern
- Raises ValueError if topic format is invalid
- Critical for security (ACL enforcement verification)

**Location in File**:
- Add after existing topic construction functions
- Group with other discovery-related topic functions
- Add appropriate docstrings following existing patterns

**Design Notes**:
- Follow existing naming conventions (get_*_topic pattern)
- Use same validation approach as existing functions
- Maintain consistency with topic structure in proposal document

---

### 2. `src/solace_agent_mesh/common/sac/sam_component_base.py`

**Changes Required**:

#### Add Trust Manager Integration

**New Instance Variables**:
- `self.trust_manager: Optional[TrustManager]` - Trust manager instance (None if disabled)

**Modifications to `__init__` Method**:

After existing initialization (after namespace and max_message_size_bytes setup):
1. Check if trust manager is enabled in config
2. If enabled, create TrustManager instance with:
   - component_id from `_get_component_id()` (new abstract method)
   - component_type from `_get_component_type()` (new abstract method)
   - namespace from config
   - config from `trust_manager` config block
   - publish_callback pointing to `self.publish_a2a_message`
   - log_identifier from `self.log_identifier`
3. Store in `self.trust_manager`
4. Log initialization at INFO level

**New Abstract Methods to Add**:

##### `@abstractmethod def _get_component_id(self) -> str`
- Returns unique identifier for this component instance
- Must be implemented by subclasses
- For agents: return agent_name
- For gateways: return gateway_id

##### `@abstractmethod def _get_component_type(self) -> str`
- Returns component type string
- Must be implemented by subclasses
- For agents: return "agent"
- For gateways: return "gateway"

**Modifications to `_async_setup_and_run` Method**:

After existing async setup, before main loop:
1. If trust_manager exists, call `await self.trust_manager.initialize()`
2. If trust_manager exists, subscribe to trust card topics
3. Log subscription at INFO level

**New Method to Add**:

##### `_subscribe_to_trust_cards(self) -> None`
- Constructs trust card subscription topic
- Adds subscription via existing subscription mechanism
- Logs subscription at DEBUG level

**Modifications to Message Routing**:

In the message processing logic (varies by subclass, but pattern to follow):
1. Check if message topic matches trust card subscription
2. If yes, route to `_handle_trust_card_message`
3. Otherwise, continue with existing routing

**New Method to Add**:

##### `async _handle_trust_card_message(self, message: SolaceMessage, topic: str) -> None`
- Extracts payload from message
- Calls `self.trust_manager.handle_trust_card(payload, topic)`
- Acknowledges message
- Logs any errors at WARNING level
- Does not raise exceptions (graceful degradation)

**Modifications to `cleanup` Method**:

Before existing cleanup:
1. If trust_manager exists, log cleanup
2. No specific cleanup needed in Phase 1 (no persistent connections)

**Design Notes**:
- Trust manager is optional (None if not configured)
- All trust manager operations are guarded by existence check
- Failures in trust card handling don't crash component
- Abstract methods force subclasses to provide identity info
- Follows existing patterns for service integration

---

### 3. `src/solace_agent_mesh/agent/sac/component.py`

**Changes Required**:

#### Implement Abstract Methods

**Add Method**:

##### `def _get_component_id(self) -> str`
- Returns `self.agent_name`
- Simple implementation

**Add Method**:

##### `def _get_component_type(self) -> str`
- Returns `"agent"`
- Simple implementation

**Modifications to Message Routing**:

In `process_event` method, add trust card routing:
1. After existing topic checks
2. Before final "unhandled topic" warning
3. Check if topic matches trust card subscription
4. If yes, schedule `_handle_trust_card_message` on async loop
5. Return early

**Design Notes**:
- Minimal changes to existing code
- Trust card handling integrated into existing event processing
- Follows same async scheduling pattern as other message types

---

### 4. `src/solace_agent_mesh/gateway/base/component.py`

**Changes Required**:

#### Implement Abstract Methods

**Add Method**:

##### `def _get_component_id(self) -> str`
- Returns `self.gateway_id`
- Simple implementation

**Add Method**:

##### `def _get_component_type(self) -> str`
- Returns `"gateway"`
- Simple implementation

**Modifications to Message Routing**:

In `_message_processor_loop` method, add trust card routing:
1. In the topic matching section
2. After discovery topic check
3. Before gateway response/status checks
4. Check if topic matches trust card subscription
5. If yes, call `await self._handle_trust_card_message(original_broker_message, topic)`
6. Set `processed_successfully = True`
7. Continue to acknowledgment

**Design Notes**:
- Minimal changes to existing code
- Trust card handling integrated into existing message loop
- Follows same async pattern as other message types
- Gateway already has async message processing

---

### 5. `src/solace_agent_mesh/agent/sac/app.py`

**Changes Required**:

#### Add Trust Manager Configuration Schema

**Add to `SamAgentAppConfig` Class**:

New field after existing service configurations:

```python
trust_manager: Optional[TrustManagerConfig] = Field(
    default=None,
    description="Configuration for the Trust Manager (component identity verification)"
)
```

**New Pydantic Model to Add** (before `SamAgentAppConfig`):

##### `TrustManagerConfig(SamConfigBase)`

**Fields**:
- `enabled: bool = Field(default=False)` - Enable/disable trust manager
- `key_storage: KeyStorageConfig` - Key storage configuration
- `card_publish_interval_seconds: int = Field(default=86400)` - Publish interval (24 hours)
- `card_expiration_days: int = Field(default=30)` - Card validity period
- `verification_mode: str = Field(default="strict")` - "strict" or "permissive"
- `clock_skew_tolerance_seconds: int = Field(default=300)` - Clock skew tolerance (5 minutes)

**New Pydantic Model to Add**:

##### `KeyStorageConfig(SamConfigBase)`

**Fields**:
- `type: str = Field(...)` - "file", "env", or "memory"
- `private_key_path: Optional[str] = Field(default=None)` - Path for file storage

**Validator**:
- `@model_validator(mode="after")` - Verify private_key_path required if type="file"

**Modifications to Subscription Generation**:

In `__init__` method, after existing subscription generation:
1. If trust_manager config exists and enabled
2. Add trust card subscription to `required_topics` list
3. Use `get_trust_card_subscription_topic(namespace)`

**Design Notes**:
- Trust manager disabled by default (opt-in)
- Configuration follows existing service patterns
- Validation ensures required fields present
- Subscriptions automatically added when enabled

---

### 6. `src/solace_agent_mesh/gateway/base/app.py`

**Changes Required**:

#### Add Trust Manager Configuration Schema

**Add to `BASE_GATEWAY_APP_SCHEMA`**:

New configuration parameters in `config_parameters` list:

```python
{
    "name": "trust_manager",
    "required": False,
    "type": "object",
    "default": None,
    "description": "Configuration for the Trust Manager (component identity verification)"
}
```

**Nested Schema for trust_manager Object**:

The trust_manager object should have same structure as agent:
- `enabled: bool` - Enable/disable (default: false)
- `key_storage: object` - Key storage config
  - `type: string` - "file", "env", or "memory"
  - `private_key_path: string` - Path (required if type="file")
- `card_publish_interval_seconds: int` - Publish interval (default: 86400)
- `card_expiration_days: int` - Card validity (default: 30)
- `verification_mode: string` - "strict" or "permissive" (default: "strict")
- `clock_skew_tolerance_seconds: int` - Clock skew (default: 300)

**Modifications to Subscription Generation**:

In `__init__` method, after existing subscription generation:
1. Check if trust_manager in resolved_app_config_block
2. If trust_manager.enabled is True
3. Add trust card subscription to `subscriptions` list
4. Use `get_trust_card_subscription_topic(self.namespace)`

**Design Notes**:
- Trust manager disabled by default (opt-in)
- Configuration follows existing gateway schema patterns
- Subscriptions automatically added when enabled
- Same configuration structure as agents for consistency

---

### 7. `src/solace_agent_mesh/agent/protocol/event_handlers.py`

**Changes Required**:

#### Add Trust Card Message Handling

**New Function to Add**:

##### `def handle_trust_card_message(component, message: SolaceMessage, topic: str) -> None`
- Extracts payload from message
- Calls component.trust_manager.handle_trust_card if trust_manager exists
- Acknowledges message
- Logs errors at WARNING level
- Does not raise exceptions
- Follows same pattern as `handle_agent_card_message`

**Modifications to `process_event` Function**:

In the topic routing section:
1. After discovery topic check
2. Before agent response/status checks
3. Add check for trust card topic
4. If matches, call `handle_trust_card_message`
5. Return early

**Design Notes**:
- Follows existing event handler patterns
- Graceful error handling
- Trust manager existence checked before use
- Message always acknowledged

---

## Configuration Examples

### Agent Configuration (YAML)

```yaml
app:
  class_name: solace_agent_mesh.agent.sac.app.SamAgentApp
  app_config:
    namespace: "myorg/production"
    agent_name: "data-analyst"
    
    # Trust Manager Configuration (Phase 1)
    trust_manager:
      enabled: true
      key_storage:
        type: "file"
        private_key_path: "/secure/keys/data-analyst.key"
      card_publish_interval_seconds: 86400  # 24 hours
      card_expiration_days: 30
      verification_mode: "strict"
      clock_skew_tolerance_seconds: 300
    
    # ... rest of agent config
```

### Gateway Configuration (YAML)

```yaml
app:
  class_name: solace_agent_mesh.gateway.http_sse.app.WebUIBackendApp
  app_config:
    namespace: "myorg/production"
    gateway_id: "web-gateway-01"
    
    # Trust Manager Configuration (Phase 1)
    trust_manager:
      enabled: true
      key_storage:
        type: "file"
        private_key_path: "/secure/keys/web-gateway-01.key"
      card_publish_interval_seconds: 86400  # 24 hours
      card_expiration_days: 30
      verification_mode: "strict"
      clock_skew_tolerance_seconds: 300
    
    # ... rest of gateway config
```

### Development Configuration (Memory Storage)

```yaml
trust_manager:
  enabled: true
  key_storage:
    type: "memory"  # Keys regenerated on restart
  card_publish_interval_seconds: 3600  # 1 hour for testing
  card_expiration_days: 1
  verification_mode: "permissive"  # Log warnings, don't fail
```

---

## Data Structures

### Trust Card JSON Format

```json
{
  "component_type": "gateway",
  "component_id": "web-gateway-01",
  "namespace": "myorg/production",
  "jwks": {
    "keys": [
      {
        "kty": "EC",
        "crv": "P-256",
        "x": "WKn-ZIGevcwGIyyrzFoZNBdaq9_TsqzGl96oc0CWuis",
        "y": "y77t-RvAHRKTsSGdIYUfweuOvwrvDD-Q3Hv5J0fSKbE",
        "use": "sig",
        "kid": "web-gateway-01-key-1704067200000",
        "alg": "ES256"
      }
    ]
  },
  "issued_at": 1704067200000,
  "expires_at": 1706659200000,
  "version": "1.0"
}
```

### JWKS Structure (RFC 7517)

```json
{
  "keys": [
    {
      "kty": "EC",           // Key Type
      "crv": "P-256",        // Curve (NIST P-256)
      "x": "base64url...",   // X coordinate
      "y": "base64url...",   // Y coordinate
      "use": "sig",          // Usage (signature)
      "kid": "key-id",       // Key ID
      "alg": "ES256"         // Algorithm
    }
  ]
}
```

---

## Topic Structure

### Trust Card Topics

**Publishing**:
- Format: `{namespace}/a2a/v1/trust/{component-type}/{client-username}`
- Example: `myorg/production/a2a/v1/trust/gateway/web-gateway-01`

**Subscription Patterns**:
- All trust cards: `{namespace}/a2a/v1/trust/*/*`
- Specific type: `{namespace}/a2a/v1/trust/gateway/*`
- Example: `myorg/production/a2a/v1/trust/*/*`

**ACL Configuration**:
```
Client "web-gateway-01":
  Publish: */a2a/v1/trust/gateway/web-gateway-01

Client "data-analyst-agent":
  Publish: */a2a/v1/trust/agent/data-analyst-agent
```

---

## Security Considerations

### Phase 1 Security Properties

1. **ACL Enforcement**: Broker ACLs prevent components from publishing trust cards with wrong component type or ID
2. **Topic Validation**: Trust Manager verifies topic matches payload before storing
3. **JWKS Validation**: Basic format validation ensures well-formed key data
4. **Expiration Checking**: Expired cards are rejected and periodically cleaned
5. **Thread Safety**: All registry operations are thread-safe

### Phase 1 Limitations

1. **No Signature Verification**: Trust cards are not self-signed or verified in Phase 1
2. **No JWT Operations**: No signing or verification of user identity claims
3. **No Key Rotation**: Single key per component, rotation deferred to future
4. **No Persistence**: Trust registry rebuilt on component restart
5. **Basic Validation**: Only format validation, not cryptographic verification

### Security Notes

- ACL configuration is the primary security mechanism in Phase 1
- Trust card payload validation prevents malformed data
- Component type from topic (not payload) used for authorization
- All validation failures logged for security monitoring
- Graceful degradation prevents DoS via malformed cards

---

## Error Handling

### Error Handling Strategy

1. **Initialization Errors**: Logged and raised (component fails to start)
2. **Key Generation Errors**: Logged and raised (component fails to start)
3. **Publishing Errors**: Logged but not raised (component continues)
4. **Reception Errors**: Logged but not raised (message acknowledged)
5. **Validation Errors**: Logged at WARNING level (card rejected)

### Logging Levels

- **DEBUG**: Routine operations (card received, validation steps)
- **INFO**: Significant events (card published, new card stored, initialization)
- **WARNING**: Validation failures, malformed cards, expired cards
- **ERROR**: Key generation failures, configuration errors
- **CRITICAL**: Not used in Phase 1

### Example Log Messages

```
INFO [TrustManager:web-gateway-01] Trust Manager initialized successfully
INFO [TrustManager:web-gateway-01] Published Trust Card to myorg/production/a2a/v1/trust/gateway/web-gateway-01
INFO [TrustRegistry] Added new trust card for component: data-analyst-agent (type: agent)
WARNING [TrustManager:web-gateway-01] Trust Card verification failed: topic component_id mismatch
WARNING [TrustRegistry] Removed expired trust card for component: old-gateway-01
ERROR [KeyManager:web-gateway-01] Failed to load private key from /secure/keys/web-gateway-01.key
```

---

## Testing Considerations

### Unit Tests Required

1. **TrustCard Model**:
   - Validation of all fields
   - Expiration checking
   - JWKS extraction
   - Serialization/deserialization

2. **TrustRegistry**:
   - Add/update operations
   - Retrieval operations
   - Thread safety
   - Expiration cleanup

3. **KeyManager**:
   - Key generation
   - File storage/loading
   - Environment variable loading
   - JWKS generation
   - Error handling

4. **TrustManager**:
   - Initialization
   - Card publishing
   - Card reception and validation
   - Topic parsing
   - Error handling

### Integration Tests Required

1. **Component Integration**:
   - Trust Manager initialization in components
   - Trust card publishing on startup
   - Periodic publishing
   - Trust card reception
   - Registry population

2. **Cross-Component**:
   - Gateway publishes, agent receives
   - Agent publishes, gateway receives
   - Multiple components exchanging cards
   - ACL enforcement (requires broker)

3. **Configuration**:
   - Enabled/disabled scenarios
   - Different storage types
   - Invalid configurations
   - Missing required fields

### Test Data

- Sample ECDSA key pairs (P-256)
- Sample trust cards (valid and invalid)
- Sample JWKS structures
- Sample topics (valid and invalid)
- Sample configurations

---

## Monitoring and Observability

### Metrics to Track

1. **Trust Cards Published**: Count of successful publications
2. **Trust Cards Received**: Count of cards received
3. **Trust Cards Stored**: Count of cards added to registry
4. **Validation Failures**: Count and reasons for failures
5. **Expired Cards Removed**: Count of cleanup operations

### Health Indicators

1. **Trust Manager Initialized**: Boolean status
2. **Key Pair Loaded**: Boolean status
3. **Registry Size**: Number of stored trust cards
4. **Last Publish Time**: Timestamp of last successful publish
5. **Last Receive Time**: Timestamp of last card received

### Debug Information

1. **Component Identity**: component_id, component_type, namespace
2. **Key ID**: Current key identifier
3. **Registry Contents**: List of known component IDs and types
4. **Configuration**: Trust manager settings (sanitized)

---

## Dependencies

### New Python Package Dependencies

1. **cryptography** (already in project):
   - Version: >=41.0.0
   - Used for: ECDSA key operations, JWKS generation
   - License: Apache 2.0 / BSD

2. **PyJWT** (new dependency):
   - Version: >=2.8.0
   - Used for: JWT operations (Phase 2, but install in Phase 1)
   - License: MIT
   - Install: `pip install PyJWT[crypto]`

3. **jwcrypto** (new dependency):
   - Version: >=1.5.0
   - Used for: JWKS operations, key format conversions
   - License: LGPL
   - Install: `pip install jwcrypto`

### Dependency Notes

- All dependencies are well-maintained, popular libraries
- Licenses are compatible with project
- Versions specified are minimum required
- Phase 2 will use PyJWT for signing/verification
- jwcrypto provides JWKS utilities

---

## Migration and Rollout

### Backward Compatibility

- Trust Manager is **opt-in** (disabled by default)
- Existing components work without modification
- No breaking changes to existing APIs
- Configuration is additive (new optional block)

### Rollout Strategy

1. **Phase 1a**: Deploy code with trust manager disabled
2. **Phase 1b**: Enable on test/dev environments
3. **Phase 1c**: Monitor trust card exchange
4. **Phase 1d**: Enable on production (one component type at a time)
5. **Phase 2**: Add JWT signing/verification

### Configuration Migration

- No migration needed (new feature)
- Components can enable independently
- No coordination required between components
- Gradual rollout supported

---

## Future Enhancements (Out of Scope for Phase 1)

### Phase 2: JWT Signing and Verification

- Implement JWT signing for user identity claims
- Implement JWT verification using trust registry
- Add signature verification for trust cards
- Complete end-to-end security flow

### Future Phases

- **Key Rotation**: Support for multiple active keys, automatic rotation
- **Trust Card Persistence**: Save/load registry from disk
- **Trust Policies**: Per-component trust configuration
- **Revocation**: Trust card revocation mechanism
- **Monitoring Dashboard**: UI for trust card status
- **Certificate Integration**: Support for X.509 certificates
- **Hardware Security**: HSM integration for key storage

---

## Appendix: File Structure

### Enterprise Repository Structure

```
src/solace_agent_mesh_enterprise/
└── common/
    └── trust/                          # NEW - All files in enterprise repo
        ├── __init__.py                 # NEW - Includes factory function
        ├── trust_card.py               # NEW
        ├── trust_registry.py           # NEW
        ├── trust_manager.py            # NEW
        ├── key_manager.py              # NEW
        └── exceptions.py               # NEW
```

### Open Source Repository (No Changes Required)

The open source repository already contains all necessary integration hooks:

```
src/solace_agent_mesh/
├── common/
│   ├── a2a/
│   │   └── protocol.py                 # Already has trust card topic functions
│   └── sac/
│       └── sam_component_base.py       # Already has trust manager hooks
├── agent/
│   ├── sac/
│   │   ├── app.py                      # Already has abstract methods
│   │   └── component.py                # Already has message routing
│   └── protocol/
│       └── event_handlers.py           # Already has trust card routing
└── gateway/
    └── base/
        ├── app.py                      # Already has abstract methods
        └── component.py                # Already has message routing
```

---

## Appendix: Key Algorithms

### ECDSA with P-256 (ES256)

**Why ES256?**
- Industry standard for JWT signing
- Smaller signatures than RSA (64 bytes vs 256 bytes)
- Faster signing and verification
- NIST-approved curve (P-256 / secp256r1)
- Wide library support

**Key Properties**:
- Curve: NIST P-256 (secp256r1)
- Key size: 256 bits
- Signature size: 64 bytes
- Algorithm identifier: ES256 (for JWT)

**Security Level**:
- Equivalent to 128-bit symmetric security
- Suitable for long-term use
- Approved by NIST, NSA Suite B

---

## Document Version

- **Version**: 1.0
- **Date**: 2025-01-15
- **Status**: Draft for Review
- **Phase**: Phase 1 (Trust Card Infrastructure)
- **Repository**: solace-agent-mesh-enterprise
- **Next Phase**: Phase 2 (JWT Signing and Verification)
