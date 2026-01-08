---
title: SQL Database Integration
sidebar_position: 40
---

# SQL Database Integration

This tutorial sets up a SQL database agent in Agent Mesh, which allows the Agent Mesh agent to answer natural language queries about a sample coffee company database. This tutorial provides some sample data to set up an SQLite database, but you can use the same approach to connect to other database types, such as MySQL or PostgreSQL.

## Prerequisites

Before starting this tutorial, ensure that you have installed and configured Agent Mesh:

- [Installed Agent Mesh and the Agent Mesh CLI](../../installing-and-configuring/installation.md)
- [Created a new Agent Mesh project](../../installing-and-configuring/run-project.md)
- Access to a SQL database (local or remote)

## Adding the SQL Database Plugin

Add the SQL Database plugin to your Agent Mesh project:

```sh
sam plugin add abc-coffee-info --plugin sam-sql-database
```
You can use any name for your agent, in this tutorial we use `abc-coffee-info`.

This command:
- Installs the `sam-sql-database` plugin
- Creates a new agent configuration file at `configs/agents/abc-coffee-info.yaml`

## Downloading Example Data

For this tutorial, you can use a sample SQLite database for a fictional coffee company called ABC Coffee Co. 

First, download the example data.

You can either visit this link to download with your browser:

  https://github.com/SolaceLabs/solace-agent-mesh-core-plugins/raw/refs/heads/main/sam-sql-database/example-data/abc_coffee_co.zip

Or you can use the command line to download the ZIP file:

#### Using wget
```sh
wget https://github.com/SolaceLabs/solace-agent-mesh-core-plugins/raw/refs/heads/main/sam-sql-database/example-data/abc_coffee_co.zip
```

#### Using curl
```sh
curl -LO https://github.com/SolaceLabs/solace-agent-mesh-core-plugins/raw/refs/heads/main/sam-sql-database/example-data/abc_coffee_co.zip
```

After downloading the ZIP file, extract it to a directory of your choice. You can use the following command to extract the ZIP file:

```sh
unzip abc_coffee_co.zip
```

## Configuring the Agent

Now, update the agent configuration to use the SQLite database and import the CSV files.
Open the `configs/agents/abc-coffee-info.yaml` file and modify the `agent_init_function.config` section to specify the CSV directory.

Here is what you need to modify in the configuration file:

```yaml
# Find the agent_init_function section and update the config:
agent_init_function:
  module: "sam_sql_database.lifecycle"
  name: "initialize_sql_agent"
  config:
    db_type: "${ABC_COFFEE_INFO_DB_TYPE}"
    db_name: "${ABC_COFFEE_INFO_DB_NAME}"
    database_purpose: "${ABC_COFFEE_INFO_DB_PURPOSE}"
    data_description: "${ABC_COFFEE_INFO_DB_DESCRIPTION}"
    # Add the CSV directory path
    csv_directories:
      - /path/to/your/unzipped/data
```

Ensure you replace `/path/to/your/unzipped/data` with the path where you extracted the example data. For example, if you put the ZIP file in the root directory of your Agent Mesh project, you can use `abc_coffee_co`.

## Setting the Environment Variables

The SQL Database agent requires that you configure several environment variables. You must create or update your `.env` file with the following variables for this tutorial:

```bash
ABC_COFFEE_INFO_DB_TYPE=sqlite
ABC_COFFEE_INFO_DB_NAME=abc_coffee.db
ABC_COFFEE_INFO_DB_PURPOSE="ABC Coffee Co. sales and operations database"
ABC_COFFEE_INFO_DB_DESCRIPTION="Contains information about ABC Coffee Co. products, sales, customers, employees, and store locations."
# You can leave other environment variables as unset or empty
```

SQLite stores the database in a local file and doesn't require a username or password for access. If you're using a database such as MySQL or PostgreSQL, you'll need to provide the appropriate environment variables for them.

## Running the Agent

Now, you can start your SQL database agent:

```sh
sam run configs/agents/abc-coffee-info.yaml
```

The agent:
1. Connects to the A2A control plane
2. Initializes the SQLite database and imports CSV data from the specified directory
3. Detects the database schema automatically
4. Registers its capabilities with the agent discovery system

## Interacting with the Database

After your SQL database agent is running, you can interact with the ABC Coffee database through any gateway in your Agent Mesh project (such as the Web UI gateway at `http://localhost:8000`).

You can ask natural language questions about the ABC Coffee Co. database, such as:

- "How many customers does ABC Coffee have?"
- "What are the top-selling products?"
- "Show me the sales by region"
- "List all orders from the last 30 days"
- "What products are currently low in inventory?"

Try creating reports by asking questions such as:

- "Create a report of our sales in 2024"
- "Generate a summary of customer demographics"

The SQL Database agent converts your natural language questions into SQL queries, executes them against the database, and returns the results. For large result sets, the agent automatically saves the results as artifacts that you can download.

## Advanced Configuration

The SQL Database plugin supports many advanced configuration options. Here is a complete example based on the plugin structure:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: abc-coffee-info.log

!include ../shared_config.yaml

apps:
  - name: abc-coffee-info-app
    app_module: solace_agent_mesh.agent.sac.app 
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "AbcCoffeeInfo"
      display_name: "ABC Coffee Database Agent"
      supports_streaming: false
      model: *general_model

      instruction: |
        You are an expert SQL assistant for the ABC Coffee Co. database.
        The database schema and query examples are provided to you.
        Your primary goal is to translate user questions into accurate SQL queries.
        If a user asks to query the database, generate the SQL and call the 'execute_sql_query' tool.
        If the 'execute_sql_query' tool returns an error, analyze the error message and the original SQL,
        then try to correct the SQL query and call the tool again.
        If the results are large and the tool indicates they were saved as an artifact, inform the user about the artifact.
        Always use the 'execute_sql_query' tool to interact with the database.

      # Agent initialization with database setup
      agent_init_function:
        module: "sam_sql_database.lifecycle"
        name: "initialize_sql_agent"
        config:
          db_type: "${ABC_COFFEE_INFO_DB_TYPE}"
          db_name: "${ABC_COFFEE_INFO_DB_NAME}"
          database_purpose: "${ABC_COFFEE_INFO_DB_PURPOSE}"
          data_description: "${ABC_COFFEE_INFO_DB_DESCRIPTION}"
          auto_detect_schema: true
          csv_directories:
            - "abc_coffee_co"  # Path to your extracted data
          query_examples:
            - natural_language: "Show all customers from New York"
              sql_query: "SELECT * FROM customers WHERE city = 'New York';"
            - natural_language: "What are the top 5 best-selling products?"
              sql_query: "SELECT product_name, SUM(quantity) as total_sold FROM order_items JOIN products ON order_items.product_id = products.id GROUP BY product_name ORDER BY total_sold DESC LIMIT 5;"

      agent_cleanup_function:
        module: "sam_sql_database.lifecycle"
        name: "cleanup_sql_agent_resources"

      # SQL query tool
      tools:
        - tool_type: python
          component_module: "sam_sql_database.tools"
          function_name: "execute_sql_query"

      session_service: *default_session_service
      artifact_service: *default_artifact_service

      # Agent capabilities - This is what other agents see during discovery
      agent_card:
        description: "ABC Coffee Co. Database Agent - Access to comprehensive coffee shop data including customers, orders, products, inventory, and sales history. Can answer questions about business metrics, customer analytics, product performance, and operational data."
        defaultInputModes: ["text"]
        defaultOutputModes: ["text", "file"]
        skills:
          - id: "sql_query"
            name: "Coffee Shop Database Query"
            description: "Queries ABC Coffee Co. database containing customer orders, product catalog, inventory levels, sales history, and employee data."

      # A2A Protocol settings
      agent_card_publishing: { interval_seconds: 30 }
      agent_discovery: { enabled: true }
      inter_agent_communication:
        allow_list: ["*"]
        request_timeout_seconds: 60
```

## Customizing the Agent Card

The `agent_card` section is crucial as it defines how other agents in your Agent Mesh ecosystem discover and understand this database agent's capabilities. When other agents use agent discovery, they can see this information to decide whether to delegate tasks to your database agent.

### Key Agent Card Elements

1. **Description**: Clearly describe what data the agent has access to and what types of questions it can answer
2. **Skills**: List specific capabilities with concrete examples that show the scope of data available
3. **Data Context**: Mention the business domain, data types, and scope of information available

### Example of a Well-Configured Agent Card

```yaml
agent_card:
  description: "ABC Coffee Co. Database Agent - Access to comprehensive coffee shop data including customers, orders, products, inventory, and sales history. Can answer questions about business metrics, customer analytics, product performance, and operational data."
  defaultInputModes: ["text"]
  defaultOutputModes: ["text", "file"]
  skills:
    - id: "sql_query"
      name: "Coffee Shop Database Query"
      description: "Queries ABC Coffee Co. database containing customer orders, product catalog, inventory levels, sales history, and employee data."
```

This detailed information helps other agents understand:
- What business domain this agent covers (coffee shop operations)
- What types of data are available (customers, orders, products, inventory, sales)
- What kinds of questions can be answered (metrics, analytics, performance data)
- Specific examples of queries that work well

When configuring your own database agent, customize the description and examples to match your specific data and use cases.
