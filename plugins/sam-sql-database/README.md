# Solace Agent Mesh - SQL Database Agent Plugin for A2A ADK Host

This plugin empowers the A2A ADK Host with natural language querying capabilities for SQL databases, supporting MySQL, PostgreSQL, and SQLite. It leverages the host's "Configurable Agent Initialization and Cleanup" feature and Google's Agent Development Kit (ADK) for its core LLM-driven logic.

## Features

*   **Natural Language to SQL:** The host ADK agent's LLM converts user questions into SQL queries.
*   **Multi-Database Support:** Works with MySQL, PostgreSQL, and SQLite.
*   **Flexible Schema Handling:**
    *   Automatic schema detection and summarization for LLM prompting.
    *   Manual override for detailed schema and natural language summaries.
*   **CSV Data Import:** Initialize database tables from CSV files at startup.
*   **Configurable Response Formatting:** Get query results in YAML, JSON, or CSV.
*   **Large Result Management:** Automatically saves large query results as ADK artifacts.
*   **Customizable LLM Interaction:** Provide database purpose, data descriptions, query examples, and response guidelines to tailor LLM behavior.


## Installation

```bash
sam plugin add <your-component-name> --plugin sam-sql-database
```

This creates a new component configuration at `configs/plugins/<your-component-name-kebab-case>.yaml`.

## Configuration

The SQL Database Agent is configured within the `apps` section of your A2A ADK Host's main YAML configuration file. A template is provided in `plugins/sam-sql-database/config.yaml`.

**Key Configuration Sections:**

### 1. Agent Initialization (`agent_init_function`)

This section configures the custom initialization logic for the SQL agent.

```yaml
# Within app_config:
agent_init_function:
  module: "sam_sql_database.lifecycle" # Path to the plugin's lifecycle module
  name: "initialize_sql_agent"        # Name of the initialization function
  # base_path: "./plugins"            # Optional: if your plugins are in a 'plugins' subdir
  config: # This is the custom_agent_init_config, validated by SqlAgentInitConfigModel
    db_type: "${DB_TYPE}"             # REQUIRED: "postgresql", "mysql", or "sqlite"
    db_host: "${DB_HOST}"             # Optional: e.g., "localhost" (required for mysql/postgres)
    db_port: ${DB_PORT}               # Optional: e.g., 5432 (required for mysql/postgres)
    db_user: "${DB_USER}"             # Optional: (required for mysql/postgres)
    db_password: "${DB_PASSWORD}"     # Optional: (required for mysql/postgres)
    db_name: "${DB_NAME}"             # REQUIRED: Database name or file path for SQLite
    query_timeout: 30                 # Optional: Default 30 seconds
    database_purpose: "Example: To store customer order and product information." # Optional
    data_description: "Example: Contains tables for customers, products, orders, and order_items. Timestamps are in UTC." # Optional
    auto_detect_schema: true          # Optional: Default true. If false, schema_override is required.
    database_schema_override: ""      # Optional: YAML/text string of schema if auto_detect_schema is false.
    schema_summary_override: ""       # Optional: Natural language summary if auto_detect_schema is false.
    query_examples:                   # Optional: List of natural language to SQL examples
      - natural_language: "Show all customers from New York"
        sql_query: "SELECT * FROM customers WHERE city = 'New York';"
    csv_files: []                     # Optional: List of CSV file paths to import on startup
    csv_directories: []               # Optional: List of directories to scan for CSVs
    response_guidelines: "Please note: Data is updated daily." # Optional
```

*   **`db_type`**: (Required) Specify `"postgresql"`, `"mysql"`, or `"sqlite"`.
*   **`db_host`**, **`db_port`**, **`db_user`**, **`db_password`**: (Required for PostgreSQL/MySQL) Connection details for your database. It's highly recommended to use environment variables (e.g., `${DB_HOST}`) for sensitive information.
*   **`db_name`**: (Required) The name of the database (for PostgreSQL/MySQL) or the file path to the database file (for SQLite).
*   **`query_timeout`**: (Optional) Timeout in seconds for SQL queries. Defaults to 30.
*   **`database_purpose`**: (Optional) A brief description of what the database is used for. Helps the LLM understand the context.
*   **`data_description`**: (Optional) A more detailed description of the data, tables, and their relationships.
*   **`auto_detect_schema`**: (Optional, default: `true`) If `true`, the plugin attempts to automatically detect the database schema. If `false`, you must provide `database_schema_override` and `schema_summary_override`.
*   **`database_schema_override`**: (Required if `auto_detect_schema` is `false`) A YAML or plain text string describing the detailed database schema (tables, columns, types, relationships).
*   **`schema_summary_override`**: (Required if `auto_detect_schema` is `false`) A concise natural language summary of the schema, suitable for direct inclusion in an LLM prompt.
*   **`query_examples`**: (Optional) A list of examples to help the LLM generate better SQL queries. Each example should have `natural_language` and `sql_query` keys.
*   **`csv_files`**: (Optional) A list of absolute or relative paths to CSV files to import into the database on startup.
*   **`csv_directories`**: (Optional) A list of directories to scan for CSV files to import.
*   **`response_guidelines`**: (Optional) Text that will be appended to the `message_to_llm` field in the `execute_sql_query` tool's response. Useful for providing disclaimers or context about the data.

### 2. Agent Cleanup (`agent_cleanup_function`)

This ensures database connections are closed properly when the agent shuts down.

```yaml
# Within app_config:
agent_cleanup_function:
  module: "sam_sql_database.lifecycle"
  name: "cleanup_sql_agent_resources"
  # base_path: "./plugins" # Optional
```

### 3. ADK Agent Configuration

*   **`model`**: Specify the ADK-compatible LLM to be used for NL-to-SQL conversion (e.g., `"gemini-1.5-flash"`).
*   **`instruction`**: Provide a system prompt for the LLM. This prompt will be dynamically augmented with the database schema (from auto-detection or overrides) and query examples.
    Example:
    ```yaml
    instruction: |
      You are an expert SQL assistant for the connected database.
      The database schema and query examples will be provided to you.
      Your primary goal is to translate user questions into accurate SQL queries.
      If a user asks to query the database, generate the SQL and call the 'execute_sql_query' tool.
      If the 'execute_sql_query' tool returns an error, analyze the error message and the original SQL,
      then try to correct the SQL query and call the tool again.
      If the results are large and the tool indicates they were saved as an artifact, inform the user about the artifact.
      Always use the 'execute_sql_query' tool to interact with the database.
    ```

### 4. Tool Configuration (`tools`)

The plugin provides one primary ADK tool:

```yaml
# Within app_config:
tools:
  - tool_type: python
    component_module: "sam_sql_database.tools" # Path to the plugin's tools module
    function_name: "execute_sql_query"
    # required_scopes: ["database:query"] # Optional: Define scopes if using authorization
```

*   **`execute_sql_query` Tool Parameters:**
    *   `query` (str, required): The SQL query string to execute.
    *   `response_format` (str, optional, default: `"yaml"`): Desired format for results (`"yaml"`, `"json"`, or `"csv"`).
    *   `inline_result` (bool, optional, default: `true`): If `true`, attempts to return results inline. If `false` or results are too large, saves them as an ADK artifact.

### 5. Host Services

Configure `session_service` and `artifact_service` in your `app_config` as needed by the A2A ADK Host. The SQL agent uses the `artifact_service` for storing large query results.

```yaml
# Within app_config:
session_service:
  type: "memory" # Or "database", "vertex"
  default_behavior: "PERSISTENT"

artifact_service:
  type: "filesystem"
  base_path: "/tmp/a2a_sql_agent_artifacts" # Example path
  artifact_scope: "app" # Or "namespace", "custom"
```

### 6. Environment Variables

Ensure the following environment variables are set in your A2A ADK Host environment, as referenced in the template:

*   `SOLACE_BROKER_URL`, `SOLACE_BROKER_VPN`, `SOLACE_BROKER_USERNAME`, `SOLACE_BROKER_PASSWORD` (for Solace connection)
*   `NAMESPACE` (your A2A topic namespace)
*   `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` (for database connection, corresponding to the placeholders in your YAML)
*   Any API keys required by your chosen LLM (e.g., `GOOGLE_API_KEY`).

## Usage

Once the A2A ADK Host is configured with the SQL Database Agent:

1.  The host starts, and the `initialize_sql_agent` function connects to the database, loads/detects the schema, and imports any specified CSV data. This schema information is stored for the ADK agent.
2.  A user sends a natural language query to the A2A ADK Host (e.g., via a gateway like Slack or WebUI).
3.  The ADK agent, using its augmented prompt (base instruction + schema + examples), converts the natural language query into an SQL query string.
4.  The ADK agent invokes the `execute_sql_query` tool with the generated SQL.
5.  The tool:
    *   Executes the SQL query against the database.
    *   Formats the results into the requested format (YAML, JSON, or CSV).
    *   If `inline_result` is true and the formatted result is small (default < 100KB), it's returned directly.
    *   Otherwise, the result is saved as an ADK artifact, and details (filename, version) are returned.
    *   Any `response_guidelines` are appended to the tool's output message.
6.  The ADK agent receives the tool's response and formulates a final natural language answer for the user, potentially mentioning if results were saved as an artifact.

## Schema Handling

*   **Automatic Detection (`auto_detect_schema: true`):** The plugin inspects the database to determine tables, columns, types, primary keys, and foreign keys. It then generates a concise summary (typically YAML format) suitable for LLM prompting.
*   **Manual Override (`auto_detect_schema: false`):**
    *   `database_schema_override`: Provide the full, detailed schema description here (e.g., DDL statements, detailed YAML).
    *   `schema_summary_override`: Provide a concise, natural language summary of the schema that will be directly used in the LLM prompt. This gives you full control over how the schema is presented to the LLM.

The schema information (either detected or provided) is crucial for the LLM to accurately convert natural language questions into valid SQL queries.

## Query Examples

Providing `query_examples` in the configuration helps the LLM understand domain-specific terminology, preferred query patterns, and how to handle complex requests for your particular database. Each example maps a natural language phrase to its corresponding SQL query.

## CSV Data Import

*   **Purpose:** Useful for initializing databases, setting up test data, or importing data from external sources at startup.
*   **Configuration:** Use `csv_files` (list of file paths) and/or `csv_directories` (list of directories to scan for `.csv` files).
*   **Table Naming:** The CSV filename (without the `.csv` extension) is used as the table name. Special characters in the filename are sanitized (e.g., replaced with underscores).
*   **Headers:** The first row of each CSV file **must** contain column headers. These headers will be used as column names in the database table.
*   **Data Types:** Columns are typically created with a generic text type to accommodate various CSV data. An `id` column (integer, primary key, auto-incrementing) is automatically added if no column named `id` (case-insensitive) exists in the CSV headers.
*   **Existing Tables:** If a table with the derived name already exists, the CSV import for that file is skipped to prevent accidental data modification.

## Large Result Handling

The `execute_sql_query` tool has an `inline_result` parameter (defaults to `true`).
*   If `true` and the formatted result is below the configured `max_inline_result_size_bytes` (default 2KB), the content is returned directly in the tool's response.
*   If `false` or if the result exceeds this size threshold, the content is saved as an ADK artifact. The tool's response will then include the `artifact_filename` and `artifact_version`, allowing the LLM to inform the user that the results were saved.

## Error Handling

*   **SQL Execution Errors:** If the `execute_sql_query` tool encounters an error while running the SQL (e.g., syntax error, table not found), it returns a structured error message to the LLM. The LLM, based on its main instruction, can then attempt to:
    *   Correct the SQL query and retry.
    *   Ask the user for clarification.
    *   Inform the user that the query could not be executed.
*   **Plugin Initialization Errors:** Errors during the `initialize_sql_agent` phase (e.g., database connection failure, critical CSV import error) are fatal and will prevent the agent host from starting correctly.
*   **Tool Errors:** Other errors within the tool (e.g., invalid `response_format`) are also returned in a structured way to the LLM.
