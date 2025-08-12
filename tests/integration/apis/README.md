# API Persistence Testing Framework

This framework provides black box testing of the Solace Agent Mesh persistence features using lightweight test components with real databases.

## Architecture Overview

The framework implements the multi-database architecture where:
- **Gateway Database**: Uses Alembic migrations for schema management
- **Agent Databases**: Use direct schema creation (no migrations)
- **Database Isolation**: Each agent has its own separate database

```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Gateway DB    │    │   Agent A DB     │    │   Agent B DB     │
│                 │    │                  │    │                  │
│ - User sessions │    │ - Session data   │    │ - Session data   │
│ - Chat history  │    │ - Messages       │    │ - Messages       │
│ - WebUI state   │    │ - Context        │    │ - Context        │
│                 │    │                  │    │                  │
│ ✓ Alembic       │    │ ✗ No migrations │    │ ✗ No migrations │
│   Migrations    │    │                  │    │                  │
└─────────────────┘    └──────────────────┘    └──────────────────┘
```

## Framework Components

### Core Infrastructure

#### `MultiDatabaseManager`
- Manages separate SQLite databases for Gateway and each Agent
- Handles Gateway migrations and Agent direct schema creation
- Provides database connections and cleanup

#### `CrossDatabaseInspector`
- Validates database architecture (Gateway migrations vs Agent direct schema)
- Verifies session linking between Gateway and Agent databases
- Checks database isolation and data integrity

#### `GatewayPersistenceAdapter`
- Wraps existing `TestGatewayComponent` with API-like interface
- Provides session creation, message sending, and session management
- Persists data to real Gateway database

### Testing Utilities

#### `persistence_assertions.py`
- Domain-specific assertions for persistence testing
- Functions like `assert_session_linking()`, `assert_database_isolation()`
- Simplifies common persistence validation patterns

#### Enhanced `conftest.py`
- Multi-database fixtures
- Extends existing integration test fixtures
- Automatic cleanup between tests

## Directory Structure

```
tests/apis/
├── conftest.py                    # Enhanced fixtures with persistence
├── infrastructure/                # Core framework components
│   ├── multi_database_manager.py # Database lifecycle management
│   ├── database_inspector.py     # Cross-database validation
│   └── gateway_persistence_adapter.py # API-like gateway interface
├── persistence/                   # Persistence-focused tests
│   ├── test_database_architecture.py  # Architecture validation
│   ├── test_session_lifecycle.py      # Session CRUD operations
│   └── test_multi_agent_isolation.py  # Multi-agent isolation
├── utils/                         # Testing utilities
│   └── persistence_assertions.py # Custom persistence assertions
└── test_framework_smoke.py       # Basic framework validation
```

## Test Categories

### 1. Database Architecture Tests
- Verify Gateway has Alembic migrations
- Verify Agents have direct schema (no migrations)
- Test database separation and connections

### 2. Session Lifecycle Tests
- Session creation and persistence
- Message storage and retrieval
- Session switching and context preservation
- Session cleanup and deletion

### 3. Multi-Agent Isolation Tests
- Database isolation between agents
- Gateway ↔ Agent session linking
- Cross-user data isolation
- Concurrent operations safety

## Usage Examples

### Basic Session Testing
```python
async def test_session_persistence(
    gateway_with_persistence,
    cross_database_inspector
):
    # Create session
    session = await gateway_with_persistence.create_session(
        user_id="test_user",
        agent_name="TestAgent"
    )
    
    # Verify persistence
    await assert_gateway_session_exists(
        cross_database_inspector,
        session.id,
        "test_user",
        "TestAgent"
    )
```

### Database Isolation Testing
```python
async def test_agent_isolation(
    gateway_with_persistence,
    cross_database_inspector
):
    # Create sessions for different agents
    session_a = await gateway_with_persistence.create_session(
        user_id="user", agent_name="AgentA"
    )
    session_b = await gateway_with_persistence.create_session(
        user_id="user", agent_name="AgentB"
    )
    
    # Verify isolation
    await assert_database_isolation(
        cross_database_inspector, "AgentA", "AgentB"
    )
```

### Architecture Validation
```python
async def test_database_architecture(
    cross_database_inspector,
    test_agents_list
):
    # Verify complete architecture
    architecture = await cross_database_inspector.verify_database_architecture(
        test_agents_list
    )
    
    assert architecture["gateway_migration_version"] is not None
    for agent in test_agents_list:
        assert "agent_sessions" in architecture["agent_schemas"][agent]
```

## Key Features

### ✅ Real Persistence Testing
- Uses actual SQLite databases with real schema
- Tests actual migration flow for Gateway
- Validates direct schema creation for Agents

### ✅ Comprehensive Isolation
- Verifies database isolation between agents
- Tests session context isolation
- Validates cross-user data separation

### ✅ Existing Infrastructure Reuse
- Leverages existing `TestGatewayComponent`
- Uses established test patterns and fixtures
- Integrates with existing LLM mocking

### ✅ Clean Test Environment
- Automatic database cleanup between tests
- Isolated test databases
- Preserves schema while clearing data

## Prerequisites

The framework requires the following dependencies:
- `aiosqlite` - For async SQLite operations
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- Existing integration test infrastructure

## Running Tests

```bash
# Run all persistence tests
python -m pytest tests/apis/ -v

# Run specific test categories
python -m pytest tests/apis/persistence/test_database_architecture.py -v
python -m pytest tests/apis/persistence/test_session_lifecycle.py -v
python -m pytest tests/apis/persistence/test_multi_agent_isolation.py -v

# Run smoke tests
python -m pytest tests/apis/test_framework_smoke.py -v
```

## Future Extensions

The framework is designed to be extensible:

1. **Agent Persistence Adapter**: Direct testing of agent-level persistence
2. **Performance Testing**: Database performance under load
3. **Migration Testing**: Testing actual Alembic migration scenarios
4. **Error Recovery**: Testing persistence during failure scenarios
5. **Multi-User Scenarios**: Complex multi-user, multi-session workflows

## Integration with Existing Tests

The framework extends the existing integration test infrastructure:
- Reuses existing fixtures from `tests/integration/conftest.py`
- Leverages `TestLLMServer` for LLM mocking
- Uses `TestGatewayComponent` for gateway functionality
- Maintains compatibility with existing test patterns

This design provides comprehensive black box testing of the persistence layer while building on the robust testing infrastructure already established in the project.