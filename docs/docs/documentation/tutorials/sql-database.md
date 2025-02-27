---
title: SQL Database Integration - sqlite3, MySQL, PostgreSQL
sidebar_position: 20
---

# SQL Database Integration

This tutorial will guide you through setting up a SQL database agent in Solace Agent Mesh (SAM) that can answer natural language queries about a sample coffee company database.

## Prerequisites

Before starting this tutorial, make sure you have:
- [Installed Solace Agent Mesh and the SAM CLI](../getting-started/installation.md)
- [Created a new Solace Agent Mesh project](../getting-started/quick-start.md)

## Installing the SQL Database Plugin

First, add the SQL Database plugin to your SAM project:

```sh
solace-agent-mesh plugin add sam_sql_database --pip -u git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-sql-database
```

## Creating a SQL Database Agent

Next, create a new agent instance based on the SQL database template:

```sh
solace-agent-mesh add agent abc_coffee_info --copy-from sam_sql_database:sql_database
```

This command will create a new configuration file at `configs/agents/abc_coffee_info.yaml`.

## Downloading Example Data

For this tutorial, we'll use a sample SQLite database for a fictional coffee company called ABC Coffee Co. Follow these steps to download the example data:

1. Visit [this link](https://download-directory.github.io/?url=https%3A%2F%2Fgithub.com%2FSolaceLabs%2Fsolace-agent-mesh-core-plugins%2Ftree%2Fmain%2Fsam-sql-database%2Fexample-data%2Fabc_coffee_co) to download the example data
2. The link will open a page allowing you to download a ZIP file containing the example data
3. Save the ZIP file to your computer
4. Unzip the file to a directory of your choice (preferably in the same directory where you'll run the agent)

## Configuring the Agent

Now you need to update the agent configuration to use the SQLite database and import the CSV files. Open the `configs/agents/abc_coffee_info.yaml` file and make the following changes:

1. Set the database type to SQLite
2. Point to the directory where you unzipped the example data

Here's what you need to modify in the configuration file:

```yaml
# Find the component_config section and update these values:
component_config:
  llm_service_topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/llm-service/request/general-good/
  embedding_service_topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/embedding-service/request/text/
  agent_name: abc_coffee_info
  db_type: sqlite
  database: /path/to/your/unzipped/data/abc_coffee.db
  query_timeout: 30
  database_purpose: "ABC Coffee Co. sales and operations database"
  data_description: "Contains information about ABC Coffee Co. products, sales, customers, employees, and store locations."
  csv_directories:
    - /path/to/your/unzipped/data
```

Make sure to replace `/path/to/your/unzipped/data` with the actual path where you unzipped the example data.

## Setting Environment Variables

The SQL Database agent requires several environment variables. Create or update your `.env` file with the following:

```
SOLACE_BROKER_URL=tcp://localhost:55555
SOLACE_BROKER_USERNAME=default
SOLACE_BROKER_PASSWORD=default
SOLACE_BROKER_VPN=default
SOLACE_AGENT_MESH_NAMESPACE=

ABC_COFFEE_INFO_DB_TYPE=sqlite
ABC_COFFEE_INFO_DB_NAME=/path/to/your/unzipped/data/abc_coffee.db
ABC_COFFEE_INFO_DB_PURPOSE="ABC Coffee Co. sales and operations database"
ABC_COFFEE_INFO_DB_DESCRIPTION="Contains information about ABC Coffee Co. products, sales, customers, employees, and store locations."
```

Again, replace `/path/to/your/unzipped/data` with the actual path to your unzipped data.

## Running the Agent

Now you can start Solace Agent Mesh with your new SQL database agent:

```sh
sam run -eb
```

The `-e` flag loads environment variables from the `.env` file, and the `-b` flag opens a browser window to the SAM web interface.

## Interacting with the Database

Once SAM is running, you can interact with the ABC Coffee database through the web interface at http://localhost:5001.

You can ask natural language questions about the ABC Coffee Co. database, such as:

- "How many customers does ABC Coffee have?"
- "What are the top-selling products?"
- "Show me the sales by region"
- "Which employees have the highest sales?"
- "What's the average order value?"

The SQL Database agent will convert your natural language questions into SQL queries, execute them against the database, and return the results.

## Database Schema

The ABC Coffee Co. database contains the following tables:

[Table names and descriptions to be filled in]

## Conclusion

You've successfully set up a SQL Database agent in Solace Agent Mesh that can answer natural language queries about the ABC Coffee Co. database. This same approach can be used to connect to other database types like MySQL and PostgreSQL by adjusting the configuration and environment variables accordingly.

For more information about the SQL Database plugin, see the [plugin README](https://github.com/SolaceLabs/solace-agent-mesh-core-plugins/blob/main/sam-sql-database/README.md).
