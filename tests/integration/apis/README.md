# FastAPI HTTP API Testing Framework

This framework provides comprehensive black box testing of the Solace Agent Mesh HTTP API endpoints using real FastAPI TestClient with multi-database support.

## Architecture Overview

The framework implements a sophisticated multi-database testing architecture with provider abstraction:
- **Database Providers**: Pluggable providers for SQLite and PostgreSQL (with testcontainers)
- **Gateway Database**: Uses Alembic migrations for schema management
- **Agent Databases**: Use direct schema creation (no migrations)
- **Database Isolation**: Each agent has its own separate database
- **HTTP Testing**: Full FastAPI TestClient integration with real HTTP endpoints

```
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI TestClient Layer                     │
│  /api/v1/sessions, /api/v1/tasks, /api/v1/feedback, etc.       │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    DatabaseProvider Factory                     │
│              (SQLite Provider | PostgreSQL Provider)            │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Gateway DB    │    │   Agent A DB     │    │   Agent B DB     │
│                 │    │                  │    │                  │
│ - Sessions      │    │ - Agent Sessions │    │ - Agent Sessions │
│ - Chat Tasks    │    │ - Agent Messages │    │ - Agent Messages │
│ - User Auth     │    │ - Context Data   │    │ - Context Data   │
│                 │    │                  │    │                  │
│ ✓ Alembic       │    │ ✗ No migrations │    │ ✗ No migrations │
│   Migrations    │    │                  │    │                  │
└─────────────────┘    └──────────────────┘    └──────────────────┘
```

## Framework Components

### Core Infrastructure

#### `DatabaseProviderFactory`
- Factory pattern for creating database providers (SQLite, PostgreSQL)
- Handles provider-specific setup and configuration
- Supports parameterized testing across multiple database types

#### `DatabaseManager`
- Unified interface for database operations across providers
- Manages both sync and async database connections
- Provides gateway and agent database access

#### `DatabaseInspector`
- Validates database architecture and schema states
- Verifies session linking between Gateway and Agent databases
- Checks database isolation and data integrity
- Provides database statistics for testing validation

#### `GatewayAdapter`
- Programmatic interface for gateway operations
- Provides session creation, message sending, and session management
- Bridges between test code and actual database operations

### HTTP Testing Integration

#### FastAPI TestClient Integration
- Uses `WebUIBackendFactory` for real FastAPI app instances
- Overrides authentication for development testing
- Supports both primary and secondary clients for multi-user testing
- Full HTTP endpoint coverage with actual API calls

#### Multi-Database Parameterization
- Tests run against both SQLite and PostgreSQL automatically
- Testcontainer integration for isolated PostgreSQL testing
- Database cleanup between tests with foreign key handling

### Testing Utilities

#### `conftest.py` - Enhanced Fixtures
- Session-scoped database providers with automatic cleanup
- Parameterized database testing across multiple providers
- Multi-user testing with secondary client support
- Automatic database cleaning between tests

#### Custom Assertions (in `utils/persistence_assertions.py`)
- Domain-specific assertions for API testing
- Database validation helpers
- Response structure validation

## Directory Structure

```
tests/integration/apis/
├── conftest.py                         # Enhanced fixtures with multi-DB support
├── infrastructure/                     # Core framework components
│   ├── database_manager.py            # Unified database management
│   ├── database_inspector.py          # Database validation and inspection
│   └── gateway_adapter.py             # Programmatic gateway operations
├── persistence/                        # API-focused persistence tests
│   ├── test_api_contract_validation.py    # API contract validation
│   ├── test_authorization_security.py     # Authorization testing
│   ├── test_chat_tasks_api.py            # Chat task endpoints
│   ├── test_data_integrity.py            # Data integrity validation
│   ├── test_data_retention.py            # Data retention policies
│   ├── test_data_validation.py           # Input validation testing
│   ├── test_end_to_end_workflows.py      # Complete workflow testing
│   ├── test_error_response_consistency.py # Error handling consistency
│   ├── test_functional_edge_cases.py     # Edge case testing
│   ├── test_generic_database_architecture.py # Database architecture
│   ├── test_multi_agent_isolation.py     # Multi-agent isolation
│   ├── test_session_lifecycle.py         # Session CRUD operations
│   ├── test_task_authorization.py        # Task-level authorization
│   ├── test_task_history_api.py          # Task history endpoints
│   ├── test_task_history_integrity.py    # Task history data integrity
│   └── test_tasks_api.py                 # Task management endpoints
├── utils/                              # Testing utilities
│   └── persistence_assertions.py      # Custom API testing assertions
├── test_feedback_api.py               # Feedback API testing
└── test_simple_framework.py          # Framework smoke tests
```

## Test Categories

### 1. HTTP API Contract Tests
- Validate all `/api/v1/sessions/*` endpoints
- Test `/api/v1/tasks/*` endpoints
- Verify `/api/v1/feedback/*` endpoints
- Response structure and status code validation

### 2. Session Lifecycle Tests
- Session creation via HTTP POST
- Message storage and retrieval via API
- Session switching and context preservation
- Session deletion and cleanup

### 3. Multi-Database Architecture Tests
- Provider factory pattern validation
- SQLite vs PostgreSQL behavior consistency
- Database migration state verification
- Agent database schema validation

### 4. Authorization and Security Tests
- User authentication override testing
- Multi-user session isolation
- Task authorization validation
- Cross-user data access prevention

### 5. Data Integrity and Validation Tests
- Input validation on all endpoints
- Database constraint enforcement
- Foreign key relationship validation
- Data retention policy compliance

### 6. Performance and Edge Case Tests
- Concurrent session operations
- Large message handling
- Error response consistency
- Edge case scenario handling

## Usage Examples

### Basic HTTP API Testing
```python
def test_create_session_via_api(api_client: TestClient):
    # Test actual HTTP endpoint
    response = api_client.post("/api/v1/sessions", json={
        "agentId": "TestAgent",
        "name": "My Test Session"
    })
    assert response.status_code == 201
    session_data = response.json()
    assert session_data["agentId"] == "TestAgent"
```

### Multi-Database Provider Testing
```python
@pytest.mark.parametrize("db_provider_type", ["sqlite", "postgresql"])
def test_session_persistence_across_databases(
    api_client: TestClient,
    database_inspector: DatabaseInspector
):
    # Test runs against both SQLite and PostgreSQL
    response = api_client.post("/api/v1/sessions", json={
        "agentId": "TestAgent"
    })
    assert response.status_code == 201
    
    # Verify in database
    sessions = database_inspector.get_gateway_sessions("sam_dev_user")
    assert len(sessions) == 1
```

### Database Architecture Validation
```python
def test_database_architecture(
    database_inspector: DatabaseInspector,
    test_agents_list: list[str]
):
    # Verify Gateway has migrations
    migration_version = database_inspector.verify_gateway_migration_state()
    assert migration_version is not None
    
    # Verify Agent schemas
    for agent in test_agents_list:
        tables = database_inspector.verify_agent_schema_state(agent)
        assert "agent_sessions" in tables
        assert "alembic_version" not in tables
```

### Programmatic Operations with GatewayAdapter
```python
def test_session_with_adapter(
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector
):
    # Create session programmatically
    session = gateway_adapter.create_session(
        user_id="test_user",
        agent_name="TestAgent"
    )
    
    # Send message
    task = gateway_adapter.send_message(session.id, "Hello world")
    
    # Verify via database inspector
    messages = database_inspector.get_session_messages(session.id)
    assert len(messages) == 2  # User + Agent response
```

### Multi-User Testing
```python
def test_user_isolation(
    api_client: TestClient,
    secondary_api_client: TestClient,
    database_inspector: DatabaseInspector
):
    # Create session for primary user
    response1 = api_client.post("/api/v1/sessions", json={"agentId": "TestAgent"})
    session1_id = response1.json()["id"]
    
    # Create session for secondary user
    response2 = secondary_api_client.post("/api/v1/sessions", json={"agentId": "TestAgent"})
    session2_id = response2.json()["id"]
    
    # Verify isolation
    primary_sessions = database_inspector.get_gateway_sessions("sam_dev_user")
    secondary_sessions = database_inspector.get_gateway_sessions("secondary_user")
    
    assert len(primary_sessions) == 1
    assert len(secondary_sessions) == 1
    assert primary_sessions[0].id != secondary_sessions[0].id
```

## Key Features

### ✅ Real HTTP API Testing
- Full FastAPI TestClient integration
- Tests actual HTTP endpoints with real requests/responses
- Authentication override for development testing
- Multi-user testing support

### ✅ Multi-Database Provider Support
- SQLite for fast local testing
- PostgreSQL with testcontainers for production-like testing
- Parameterized tests run against all providers automatically
- Provider factory pattern for extensibility

### ✅ Comprehensive Database Testing
- Real database operations with actual schemas
- Migration validation for Gateway
- Direct schema validation for Agents
- Database isolation verification

### ✅ Production-Grade Test Infrastructure
- Automatic database cleanup between tests
- Foreign key constraint handling
- Concurrent testing support
- Container lifecycle management

## Prerequisites

The framework requires the following dependencies:
- `fastapi` - Web framework being tested
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `sqlalchemy` - Database operations
- `aiosqlite` - Async SQLite operations
- `testcontainers` - PostgreSQL container testing
- `psycopg2` - PostgreSQL driver
- Existing `sam-test-infrastructure` for FastAPI factory

## Running Tests

```bash
# Run all API tests
python -m pytest tests/integration/apis/ -v

# Run against specific database provider
python -m pytest tests/integration/apis/ -v --db-provider=sqlite
python -m pytest tests/integration/apis/ -v --db-provider=postgresql

# Run specific test categories
python -m pytest tests/integration/apis/persistence/test_session_lifecycle.py -v
python -m pytest tests/integration/apis/persistence/test_task_history_api.py -v
python -m pytest tests/integration/apis/persistence/test_authorization_security.py -v

# Run multi-database parameterized tests
python -m pytest tests/integration/apis/persistence/test_generic_database_architecture.py -v

# Run framework smoke tests
python -m pytest tests/integration/apis/test_simple_framework.py -v

# Run with verbose output for debugging
python -m pytest tests/integration/apis/ -v -s
```

## Configuration

### Database Provider Selection
By default, tests run against both SQLite and PostgreSQL. You can control this via:

1. **Pytest parameters** (in conftest.py):
```python
@pytest.fixture(scope="session", params=["sqlite", "postgresql"])
def db_provider_type(request):
    return request.param
```

2. **Environment variables** (if implemented):
```bash
export SAM_TEST_DB_PROVIDER=sqlite  # or postgresql
```

3. **Fixture overrides** in specific test files:
```python
@pytest.fixture(scope="session")
def db_provider_type():
    return "sqlite"  # Force SQLite only for this test file
```

## Extending the Framework

### Adding New Database Providers
```python
class MySQLProvider(DatabaseProvider):
    def setup(self, agent_names: List[str], **kwargs):
        # Implement MySQL setup
        pass
    
    # Implement other abstract methods...

# Register in factory
DatabaseProviderFactory.PROVIDERS["mysql"] = MySQLProvider
```

### Adding New Test Categories
1. Create new test file in `persistence/`
2. Use existing fixtures: `api_client`, `database_manager`, `gateway_adapter`, `database_inspector`
3. Follow existing patterns for HTTP endpoint testing

### Custom Assertions
Add domain-specific assertions to `utils/persistence_assertions.py`:
```python
def assert_valid_session_response(response_data: dict):
    assert "id" in response_data
    assert "agentId" in response_data
    assert "createdTime" in response_data
    # Add more validations...
```

## Integration with Existing Infrastructure

The framework integrates seamlessly with existing Solace Agent Mesh infrastructure:
- Uses `WebUIBackendFactory` from `sam-test-infrastructure`
- Leverages existing FastAPI application and routes
- Integrates with existing authentication system (with override)
- Uses actual database schemas and migrations
- Compatible with existing Docker/container infrastructure

## Performance Considerations

- **SQLite**: Fast startup, good for unit-style API tests
- **PostgreSQL**: Slower startup but more production-like, good for integration tests
- **Testcontainers**: Automatic cleanup but requires Docker
- **Parallel Testing**: Supported with proper database isolation

## Troubleshooting

### Common Issues

1. **PostgreSQL container startup failures**:
   - Ensure Docker is running
   - Check available ports
   - Verify testcontainers permissions

2. **Database connection errors**:
   - Check database provider initialization
   - Verify engine disposal in teardown
   - Ensure proper async/sync engine usage

3. **Foreign key constraint violations**:
   - Check database cleanup order
   - Verify constraint handling in provider

4. **Authentication override not working**:
   - Ensure dependency override is properly applied
   - Check FastAPI app initialization order

### Debug Mode
```bash
# Run with extra logging
python -m pytest tests/integration/apis/ -v -s --log-cli-level=DEBUG

# Run single test for debugging
python -m pytest tests/integration/apis/test_simple_framework.py::test_database_initialization_and_connections -v -s
```

This framework provides a robust foundation for testing the Solace Agent Mesh HTTP API with comprehensive database support and production-grade testing practices.
