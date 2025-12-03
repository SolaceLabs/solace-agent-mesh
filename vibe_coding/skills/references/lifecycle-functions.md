# Lifecycle Functions

Guide to implementing lifecycle functions for SAM agent plugins.

## Overview

Lifecycle functions manage resources that persist for the agent's lifetime:
- `agent_init_function` - Runs when agent starts
- `agent_cleanup_function` - Runs when agent shuts down

## Initialization Function

### Basic Pattern

```python
from typing import Any
from pydantic import BaseModel, Field
from solace_ai_connector.common.log import log

class AgentInitConfig(BaseModel):
    """Configuration for agent initialization."""
    startup_message: str = Field(description="Message to log on startup")
    log_level: str = Field(default="INFO", description="Logging level")

def initialize_agent(host_component: Any, init_config: AgentInitConfig):
    """
    Initialize the agent.

    Args:
        host_component: The agent host component
        init_config: Validated initialization configuration
    """
    log_identifier = f"[{host_component.agent_name}:init]"
    log.info(f"{log_identifier} Starting initialization...")
    log.info(f"{log_identifier} {init_config.startup_message}")

    # Initialize resources (database connections, API clients, etc.)
    # Store shared state
    host_component.set_agent_specific_state("initialized_at", datetime.now().isoformat())
    host_component.set_agent_specific_state("request_count", 0)

    log.info(f"{log_identifier} Initialization completed")
```

### YAML Configuration

```yaml
app_config:
  agent_init_function:
    module: "my_plugin.lifecycle"
    name: "initialize_agent"
    base_path: .
    config:
      startup_message: "Agent is starting..."
      log_level: "INFO"
```

## Cleanup Function

### Basic Pattern

```python
def cleanup_agent(host_component: Any):
    """
    Clean up resources when agent shuts down.

    Args:
        host_component: The agent host component
    """
    log_identifier = f"[{host_component.agent_name}:cleanup]"
    log.info(f"{log_identifier} Starting cleanup...")

    # Retrieve state for logging
    request_count = host_component.get_agent_specific_state("request_count", 0)
    log.info(f"{log_identifier} Processed {request_count} requests")

    # Clean up resources
    # - Close database connections
    # - Shut down background tasks
    # - Save final state

    log.info(f"{log_identifier} Cleanup completed")
```

### YAML Configuration

```yaml
app_config:
  agent_cleanup_function:
    module: "my_plugin.lifecycle"
    name: "cleanup_agent"
    base_path: .
```

## Using Agent State

The `host_component` provides methods for managing persistent state:

```python
# Set state
host_component.set_agent_specific_state("key", value)

# Get state
value = host_component.get_agent_specific_state("key", default_value)

# Access agent name
agent_name = host_component.agent_name
```

## Common Use Cases

### Database Connection Pool

```python
import aiomysql

class DBInitConfig(BaseModel):
    host: str
    port: int = 3306
    user: str
    password: str
    database: str

async def initialize_db_agent(host_component: Any, init_config: DBInitConfig):
    """Initialize with database connection pool."""
    pool = await aiomysql.create_pool(
        host=init_config.host,
        port=init_config.port,
        user=init_config.user,
        password=init_config.password,
        db=init_config.database,
    )
    host_component.set_agent_specific_state("db_pool", pool)
    log.info("Database pool created")

async def cleanup_db_agent(host_component: Any):
    """Close database pool."""
    pool = host_component.get_agent_specific_state("db_pool")
    if pool:
        pool.close()
        await pool.wait_closed()
        log.info("Database pool closed")
```

### API Client Initialization

```python
import httpx

class APIInitConfig(BaseModel):
    api_base_url: str
    api_key: str
    timeout: int = 30

def initialize_api_agent(host_component: Any, init_config: APIInitConfig):
    """Initialize with API client."""
    client = httpx.AsyncClient(
        base_url=init_config.api_base_url,
        headers={"Authorization": f"Bearer {init_config.api_key}"},
        timeout=init_config.timeout,
    )
    host_component.set_agent_specific_state("api_client", client)
    log.info("API client initialized")

async def cleanup_api_agent(host_component: Any):
    """Close API client."""
    client = host_component.get_agent_specific_state("api_client")
    if client:
        await client.aclose()
        log.info("API client closed")
```

## Best Practices

1. **Use Pydantic models** for init_config validation
2. **Log all lifecycle events** for debugging
3. **Handle errors gracefully** in initialization
4. **Clean up resources** in reverse order of creation
5. **Store shared resources** in agent state
6. **Don't block** - keep initialization quick
7. **Test lifecycle functions** independently with mocks
