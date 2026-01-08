---
title: MongoDB Integration
sidebar_position: 50
---

# MongoDB Integration

This tutorial sets up a MongoDB agent in Agent Mesh, which allows the Agent Mesh agent to answer natural language queries about a Mongo database. The agent translates user questions into MongoDB aggregation pipelines and executes them against your database.

## Prerequisites

Before starting this tutorial, ensure that you have installed and configured Agent Mesh:

- [Installed Agent Mesh and the Agent Mesh CLI](../../installing-and-configuring/installation.md)
- [Created a new Agent Mesh project](../../installing-and-configuring/run-project.md)
- Access to a MongoDB database (local or remote)

## Adding the MongoDB Plugin

Add the MongoDB plugin to your Agent Mesh project:

```sh
sam plugin add coffee-shop-mongo --plugin sam-mongodb
```

You can use any name for your agent, in this tutorial we use `coffee-shop-mongo`.

This command:
- Installs the `sam-mongodb` plugin
- Creates a new agent configuration file at `configs/agents/coffee-shop-mongo.yaml`


#### Setting Up Your MongoDB Database

This tutorial assumes you have a MongoDB database with a collection containing coffee shop data. You can use any MongoDB database, but here is an example structure for a coffee shop:

#### Example Document Structure

```json
{
  "_id": "64a1b2c3d4e5f6789012345",
  "order_id": "ORD-2024-001",
  "customer": {
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "+1-555-0123"
  },
  "items": [
    {
      "product": "Espresso",
      "quantity": 2,
      "price": 3.50,
      "category": "Coffee"
    },
    {
      "product": "Croissant",
      "quantity": 1,
      "price": 2.75,
      "category": "Pastry"
    }
  ],
  "total_amount": 9.75,
  "order_date": "2024-01-15T10:30:00Z",
  "status": "completed",
  "payment_method": "credit_card",
  "location": "Downtown Store"
}
```

## Configuring the Agent

Open the `configs/agents/coffee-shop-mongo.yaml` file and modify the `agent_init_function.config` section to connect to your MongoDB database.

Here is what you need to modify in the configuration file:

```yaml
# Find the agent_init_function section and update the config:
agent_init_function:
  module: "sam_mongodb.lifecycle"
  name: "initialize_mongo_agent"
  config:
    db_host: "${COFFEE_SHOP_MONGO_MONGO_HOST}"
    db_port: ${COFFEE_SHOP_MONGO_MONGO_PORT}
    db_user: "${COFFEE_SHOP_MONGO_MONGO_USER}"
    db_password: "${COFFEE_SHOP_MONGO_MONGO_PASSWORD}"
    db_name: "${COFFEE_SHOP_MONGO_MONGO_DB}"
    database_collection: "${COFFEE_SHOP_MONGO_MONGO_COLLECTION}"
    database_purpose: "${COFFEE_SHOP_MONGO_DB_PURPOSE}"
    data_description: "${COFFEE_SHOP_MONGO_DB_DESCRIPTION}"
    auto_detect_schema: true
    max_inline_results: 10
```

#### Setting the Environment Variables

The MongoDB agent requires several environment variables. Create or update your `.env` file with the following variables:

```bash
# MongoDB Connection Settings
COFFEE_SHOP_MONGO_MONGO_HOST=localhost
COFFEE_SHOP_MONGO_MONGO_PORT=27017
COFFEE_SHOP_MONGO_MONGO_USER=your_username
COFFEE_SHOP_MONGO_MONGO_PASSWORD=your_password
COFFEE_SHOP_MONGO_MONGO_DB=coffee_shop
COFFEE_SHOP_MONGO_MONGO_COLLECTION=orders

# Database Description
COFFEE_SHOP_MONGO_DB_PURPOSE="Coffee shop order management database"
COFFEE_SHOP_MONGO_DB_DESCRIPTION="Contains customer orders, product information, sales data, and transaction history for a coffee shop business."

# Optional Settings
AUTO_DETECT_SCHEMA=true
MAX_INLINE_RESULTS=10
```

#### MongoDB Connection Options

- **Local MongoDB**: Use `localhost` as the host and default port `27017`
- **MongoDB Atlas**: Use your Atlas connection string format
- **Authentication**: Provide username and password if your MongoDB requires authentication
- **No Authentication**: Leave username and password empty for local development databases

## Running the Agent

Now you can start your MongoDB agent:

```sh
sam run configs/agents/coffee-shop-mongo.yaml
```

The agent:
1. Connects to the A2A control plane
2. Initializes the MongoDB connection
3. Detects the database schema automatically
4. Registers its capabilities with the agent discovery system

## Interacting with the Database

After your MongoDB agent is running, you can interact with the database through any gateway in your Agent Mesh project (such as the Web UI gateway at `http://localhost:8000`).

You can ask natural language questions about your MongoDB database, such as:

- "How many orders were placed today?"
- "What are the most popular coffee products?"
- "Show me all orders from customers in New York"
- "What's the average order value this month?"
- "Find all incomplete orders"
- "Group orders by payment method and show totals"

Try creating reports by asking questions such as:

- "Create a sales report for the last 7 days"
- "Generate a summary of customer preferences"
- "Show me the top 10 customers by total spending"

The MongoDB agent converts your natural language questions into MongoDB aggregation pipelines, executes them against the database, and returns the results. For large result sets, the agent automatically saves the results as artifacts that you can download.

## Advanced Configuration

The MongoDB plugin supports many advanced configuration options. Here is a complete example based on the plugin structure:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: coffee-shop-mongo.log

!include ../shared_config.yaml

apps:
  - name: coffee-shop-mongo-app
    app_module: solace_agent_mesh.agent.sac.app 
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "CoffeeShopMongo"
      display_name: "Coffee Shop MongoDB Agent"
      supports_streaming: false
      model: *general_model

      instruction: |
        You are an expert MongoDB assistant for the coffee shop database.
        Your primary goal is to translate user questions into accurate MongoDB aggregation pipelines.
        When asked to query the database, generate the pipeline and call the query tool.
        If the tool returns an error, analyze the error message and the original pipeline,
        then try to correct the pipeline and call the tool again.
        Always provide clear explanations of the results you find.

      # Agent initialization with database setup
      agent_init_function:
        module: "sam_mongodb.lifecycle"
        name: "initialize_mongo_agent"
        config:
          db_host: "${COFFEE_SHOP_MONGO_MONGO_HOST}"
          db_port: ${COFFEE_SHOP_MONGO_MONGO_PORT}
          db_user: "${COFFEE_SHOP_MONGO_MONGO_USER}"
          db_password: "${COFFEE_SHOP_MONGO_MONGO_PASSWORD}"
          db_name: "${COFFEE_SHOP_MONGO_MONGO_DB}"
          database_collection: "${COFFEE_SHOP_MONGO_MONGO_COLLECTION}"
          database_purpose: "${COFFEE_SHOP_MONGO_DB_PURPOSE}"
          data_description: "${COFFEE_SHOP_MONGO_DB_DESCRIPTION}"
          auto_detect_schema: true
          max_inline_results: 10

      agent_cleanup_function:
        module: "sam_mongodb.lifecycle"
        name: "cleanup_mongo_agent_resources"

      # MongoDB query tool
      tools:
        - tool_type: builtin-group
          group_name: "artifact_management"
        - tool_type: builtin-group
          group_name: "data_analysis"
        - tool_type: python
          component_module: "sam_mongodb.search_query"
          function_name: "mongo_query"
          tool_config:
            collection: "${COFFEE_SHOP_MONGO_MONGO_COLLECTION}"

      session_service: *default_session_service
      artifact_service: *default_artifact_service

      # Artifact handling
      artifact_handling_mode: "reference"
      enable_embed_resolution: true
      enable_artifact_content_instruction: true

      # Agent capabilities - This is what other agents see during discovery
      agent_card:
        description: "Coffee Shop MongoDB Agent - Access to comprehensive coffee shop order data including customer information, product details, sales transactions, and order history. Can answer questions about sales analytics, customer behavior, product performance, and business metrics."
        defaultInputModes: ["text"]
        defaultOutputModes: ["text", "file"]
        skills:
          - id: "mongo_query"
            name: "Coffee Shop MongoDB Query"
            description: "Queries coffee shop MongoDB database containing customer orders, product catalog, payment transactions, and order history using aggregation pipelines."

      # A2A Protocol settings
      agent_card_publishing: { interval_seconds: 30 }
      agent_discovery: { enabled: true }
      inter_agent_communication:
        allow_list: ["*"]
        request_timeout_seconds: 60
```

## Customizing the Agent Card

The `agent_card` section is crucial as it defines how other agents in your Agent Mesh ecosystem discover and understand this MongoDB agent's capabilities. When other agents use agent discovery, they can see this information to decide whether to delegate tasks to your database agent.

### Key Agent Card Elements

1. **Description**: Clearly describe what data the agent has access to and what types of questions it can answer
2. **Skills**: List specific capabilities with concrete examples that show the scope of data available
3. **Data Context**: Mention the business domain, data types, and scope of information available

### Example of a Well-Configured Agent Card

```yaml
agent_card:
  description: "Coffee Shop MongoDB Agent - Access to comprehensive coffee shop order data including customer information, product details, sales transactions, and order history. Can answer questions about sales analytics, customer behavior, product performance, and business metrics."
  defaultInputModes: ["text"]
  defaultOutputModes: ["text", "file"]
  skills:
    - id: "mongo_query"
      name: "Coffee Shop MongoDB Query"
      description: "Queries coffee shop MongoDB database containing customer orders, product catalog, payment transactions, and order history using aggregation pipelines."
```

This detailed information helps other agents understand:
- What business domain this agent covers (coffee shop operations)
- What types of data are available (orders, customers, products, payments)
- What kinds of questions can be answered (analytics, behavior, performance, metrics)
- Specific examples of queries that work well with MongoDB aggregation pipelines

When configuring your own MongoDB agent, customize the description and examples to match your specific data structure and use cases.

## MongoDB Query Features

The MongoDB agent supports various types of queries through natural language:

### Aggregation Queries
- "Show me the top 5 products by sales volume"
- "Calculate the average order value by customer segment"
- "Group orders by month and show revenue trends"

### Filtering and Search
- "Find all orders placed in the last 24 hours"
- "Show me orders with a total amount greater than $50"
- "Find customers who ordered espresso drinks"

### Complex Analytics
- "What's the conversion rate from browsing to purchase?"
- "Show me the busiest hours of the day"
- "Calculate customer lifetime value"

### Output Formats

The agent supports multiple output formats:
- **JSON**: Default format, good for structured data
- **YAML**: Human-readable format
- **CSV**: Suitable for spreadsheet import
- **Markdown**: Formatted for documentation

You can specify the format in your query: "Show me today's sales in CSV format"

## Troubleshooting

### Common Issues and Solutions

#### Connection Errors
**Issue**: "Unable to connect to MongoDB" errors
**Solution**:
- Verify your MongoDB server is running
- Check connection parameters (host, port, credentials)
- Ensure network connectivity and firewall settings
- Test connection using MongoDB client tools

#### Authentication Errors
**Issue**: "Authentication failed" errors
**Solution**:
- Verify username and password are correct
- Check that the user has appropriate database permissions
- Ensure the authentication database is correct

#### Query Errors
**Issue**: "Invalid aggregation pipeline" errors
**Solution**:
- The agent automatically retries with corrected pipelines
- Check that your natural language query is clear and specific
- Verify that referenced fields exist in your collection

#### Schema Detection Issues
**Issue**: Agent does not understand your data structure
**Solution**:
- Ensure `auto_detect_schema` is set to `true`
- Provide detailed `data_description` in your configuration
- Check that your collection has representative sample documents
