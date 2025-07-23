# sam-mongodb SAM Plugin

A plugin that provides a MongoDB agent to perform complex queries based on natural language.

This plugin enables Solace Agent Mesh (SAM) agents to interact with MongoDB databases through natural language queries. The agent translates user questions into MongoDB aggregation pipelines and executes them, returning results in various formats.

## Features

- **Natural Language to MongoDB**: Converts user queries into MongoDB aggregation pipelines
- **Lifecycle Management**: Efficient database connection management with initialization and cleanup
- **Schema Auto-Detection**: Automatically detects and summarizes database schema for better LLM context
- **Multiple Output Formats**: Supports JSON, YAML, CSV, and Markdown output formats
- **Artifact Management**: Large results are saved as artifacts for efficient handling
- **Configurable Collection Targeting**: Can target specific collections or query across all collections

## Architecture

The plugin follows a modern, tool-based architecture with clear separation of concerns:

- **`lifecycle.py`**: Manages agent initialization and cleanup, including database connections and schema detection
- **`search_query.py`**: Contains the main `mongo_query` tool that executes aggregation pipelines
- **`services/database_service.py`**: Encapsulates all MongoDB operations and connection management

## Installation

```bash
sam plugin add <your-component-name> --plugin sam-mongodb
```

This creates a new component configuration at `configs/plugins/<your-component-name-kebab-case>.yaml`.

## Configuration

### Environment Variables

Set the following environment variables for your MongoDB connection:

```bash
export MONGO_HOST="localhost"
export MONGO_PORT=27017
export MONGO_USER="your_username"
export MONGO_PASSWORD="your_password"
export MONGO_DB="your_database"
export MONGO_COLLECTION="your_collection"
export DB_PURPOSE="Description of your database purpose"
export DB_DESCRIPTION="Detailed description of your data"
```

### Agent Configuration

The plugin uses agent lifecycle functions for efficient resource management. Key configuration sections:

#### Agent Initialization
```yaml
agent_init_function:
  module: "sam_mongodb.lifecycle"
  name: "initialize_mongo_agent"
  config:
    db_host: "${MONGO_HOST}"
    db_port: ${MONGO_PORT}
    db_user: "${MONGO_USER}"
    db_password: "${MONGO_PASSWORD}"
    db_name: "${MONGO_DB}"
    database_collection: "${MONGO_COLLECTION}"
    database_purpose: "${DB_PURPOSE}"
    data_description: "${DB_DESCRIPTION}"
    auto_detect_schema: true
    max_inline_results: 10
```

#### Tool Configuration
```yaml
tools:
  - tool_type: python
    component_module: "sam_mongodb.search_query"
    function_name: "mongo_query"
    tool_config:
      collection: "${MONGO_COLLECTION}"
```

## Example Queries

The agent can handle various types of MongoDB queries:

- **Aggregation queries**: "Show me the top 5 products by sales"
- **Filtering**: "Find all users registered in the last 30 days"
- **Grouping**: "Group orders by status and count them"
- **Complex pipelines**: "Calculate average order value by customer segment"
