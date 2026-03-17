# SAM Migration Testing Infrastructure

Component-agnostic database migration testing for all Solace Agent Mesh components.

**Uses testcontainers** - fully automated, no manual Docker commands needed.

## Structure

```
tests/integration/migrations/
├── conftest.py                 # Shared fixtures (automatic containers!)
├── common/                     # Shared utilities for all components
│   ├── db_utils.py            # Database inspection helpers
│   └── migration_helpers.py   # Alembic operation helpers
│
├── gateway/                    # Gateway WebUI migrations
│   ├── conftest.py            # Gateway-specific config
│   └── test_migration_sequence.py
│
├── adk/                       # ADK migrations (future)
│   └── ...
│
└── platform/                  # Platform services migrations (future)
    └── ...
```

## Quick Start

### 1. Install Dependencies
```bash
pip install pytest testcontainers[postgres] testcontainers[mysql] pymysql psycopg2-binary
```

### 2. Run Tests
```bash
# Test specific component (containers start automatically)
pytest tests/integration/migrations/gateway/ -v

# Test all components
pytest tests/integration/migrations/ -v

# Test specific dialect
pytest tests/integration/migrations/gateway/ -v -k "PostgreSQL"
pytest tests/integration/migrations/gateway/ -v -k "MySQL"
pytest tests/integration/migrations/gateway/ -v -k "SQLite"
```

**That's it!** Containers automatically:
- ✅ Start on first test
- ✅ Reuse across tests (session scope)
- ✅ Stop when tests finish
- ✅ Clean up completely

### No Manual Commands Needed
- ❌ No `docker-compose up`
- ❌ No `docker-compose down`
- ❌ No port conflicts
- ❌ No leftover containers

## How It Works

### Testcontainers Magic

```python
# conftest.py
@pytest.fixture(scope="session")
def postgres_container():
    postgres = PostgresContainer("postgres:15-alpine")
    postgres.start()  # Automatic!
    yield postgres
    postgres.stop()   # Automatic cleanup!
```

**When you run tests:**
1. First PostgreSQL test → Container starts
2. All PostgreSQL tests → Use same container
3. Tests finish → Container stops & removed
4. Same for MySQL

**Benefits:**
- Random ports (no conflicts)
- Fresh containers every run
- Works in CI/CD without changes
- No manual cleanup needed

## Components

### Gateway WebUI
- **Migrations**: `src/solace_agent_mesh/gateway/http_sse/alembic/`
- **Tests**: `tests/integration/migrations/gateway/`
- **Status**: ✅ Infrastructure ready

### ADK (Future)
- **Migrations**: `src/solace_agent_mesh/agent/adk/alembic/`
- **Tests**: `tests/integration/migrations/adk/` (to be created)

### Platform Services (Future)
- **Migrations**: `src/solace_agent_mesh/services/platform/alembic/`
- **Tests**: `tests/integration/migrations/platform/` (to be created)

## Adding a New Component

### 1. Create component directory
```bash
mkdir tests/integration/migrations/adk
```

### 2. Create `conftest.py`
```python
# tests/integration/migrations/adk/conftest.py
from pathlib import Path
import pytest
from alembic.config import Config

@pytest.fixture
def alembic_config(dialect_db):
    """Alembic config for ADK migrations."""
    config = Config()

    script_location = str(
        Path(__file__).parent.parent.parent.parent.parent
        / "src" / "solace_agent_mesh" / "agent" / "adk" / "alembic"
    )

    config.set_main_option("script_location", script_location)
    config.set_main_option("sqlalchemy.url", dialect_db)
    config.attributes["quiet"] = True

    return config
```

### 3. Create tests
```python
# tests/integration/migrations/adk/test_adk_migrations.py
import pytest
from alembic import command

class TestADKMigrations:
    def test_upgrade_to_head(self, alembic_config, db_engine):
        command.upgrade(alembic_config, "head")
        # Verify ADK tables exist
```

### 4. Run
```bash
pytest tests/integration/migrations/adk/ -v
# Containers start automatically!
```

## Shared Fixtures

All component tests inherit these from `conftest.py`:

### Container Fixtures (session scope)
- `postgres_container` - PostgreSQL 15 container
- `mysql_container` - MySQL 8.0 container
- `postgres_url` - PostgreSQL connection URL
- `mysql_url` - MySQL connection URL

### Database Fixtures (test scope)
- `clean_sqlite_db` - Fresh SQLite in-memory database
- `clean_postgres_db` - Clean PostgreSQL schema
- `clean_mysql_db` - Clean MySQL schema
- `dialect_db` - Parametrized across all 3 dialects
- `db_engine` - SQLAlchemy engine
- `db_inspector` - SQLAlchemy inspector

## Shared Utilities

### `common/db_utils.py`
```python
from tests.integration.migrations.common.db_utils import (
    get_table_names,
    verify_table_exists,
    verify_column_exists,
    verify_index_exists,
)
```

### `common/migration_helpers.py`
```python
from tests.integration.migrations.common.migration_helpers import (
    get_all_revisions,
    upgrade_to_revision,
    downgrade_to_revision,
)
```

## Debugging

### View Container Logs
Containers are managed by pytest - check test output for container info.

```bash
# Run with verbose output
pytest tests/integration/migrations/gateway/ -vv -s
```

### Keep Containers Running
For debugging, use `--keepalive` flag (if available) or modify fixtures:

```python
@pytest.fixture(scope="session")
def postgres_container():
    postgres = PostgresContainer("postgres:15-alpine")
    postgres.start()
    yield postgres
    # Comment out for debugging:
    # postgres.stop()
```

### Connect to Running Container
While tests are running (in another terminal):
```bash
# Find container
docker ps | grep postgres

# Connect
docker exec -it <container-id> psql -U test -d sam_test
```

## CI/CD Integration

```yaml
# .github/workflows/test-migrations.yml
jobs:
  test-migrations:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pytest testcontainers[postgres] testcontainers[mysql]
          pip install pymysql psycopg2-binary

      - name: Run migration tests
        run: |
          pytest tests/integration/migrations/gateway/ -v

      # No cleanup needed - testcontainers handles it!
```

## Troubleshooting

### "Docker not available"
Testcontainers requires Docker to be running:
```bash
# Check Docker is running
docker ps

# Start Docker Desktop (macOS) or Docker daemon (Linux)
```

### Slow first run
First run downloads container images:
- postgres:15-alpine (~80MB)
- mysql:8.0 (~500MB)

Subsequent runs are fast (images cached).

### Port conflicts
Testcontainers uses **random ports** - no conflicts!

### Container cleanup
If containers don't clean up:
```bash
# Find testcontainers
docker ps -a | grep testcontainers

# Force remove
docker rm -f $(docker ps -aq --filter "label=org.testcontainers")
```

## Performance Tips

### Session Scope (Default)
Containers start once per test session, reused across tests:
```python
@pytest.fixture(scope="session")  # ← Reuse container
def postgres_container():
    ...
```

**Pros**: Fast (container starts once)
**Cons**: Tests share container (but we clean schemas between tests)

### Function Scope (Optional)
For complete isolation, use function scope:
```python
@pytest.fixture(scope="function")  # ← New container per test
def postgres_container():
    ...
```

**Pros**: Perfect isolation
**Cons**: Much slower (container restart for each test)

**Recommendation**: Keep session scope, we clean schemas anyway.

## Next Steps

1. ✅ Infrastructure created (testcontainers-based)
2. ⏭️ Run tests: `pytest tests/integration/migrations/gateway/ -v`
3. ⏭️ Fix the 3 critical issues
4. ⏭️ Re-run tests to verify fixes