---
title: Agents
sidebar_position: 20
---

# Agents

Agents are specialized processing units within the Solace Agent Mesh framework that are built around the Google Agent Development Kit (ADK) and provide the core intelligence layer. They:

* perform specific tasks or provide domain-specific knowledge or capabilities
* integrate with the ADK runtime for advanced AI capabilities including tool usage, memory management, and session handling
* play a crucial role in the system's ability to handle a wide range of tasks and adapt to various domains

:::tip[In one sentence]
Agents are intelligence units that communicate through the A2A protocol to provide system capabilities beyond basic orchestrator capabilities.
:::

## Key Functions

1. **ADK Integration**: Agents are built using the Google Agent Development Kit, providing advanced AI capabilities including tool usage, memory management, and artifact handling.

2. **AI-Enabled**: Agents come packaged with access to large language models (LLMs) and can utilize various tools.
3. **Dynamic Discovery**: New agents can self-register/deregister and be discovered dynamically through broadcast messages without requiring changes to the running system.

4. **Tool Ecosystem**: Agents have access to built-in tools for artifact management, data analysis, web scraping, and peer-to-peer delegation.

5. **Session Management**: Agents support conversation continuity through ADK's session management capabilities.

6. **Independence**: Agents are modularized and can be updated or replaced independently of other components.


## Agent Design

Agents in Solace Agent Mesh are built around the Solace AI Connector (SAC) component with ADK. Agent Mesh agents are complete self-contained units that can carry out specific tasks or provide domain-specific knowledge or capabilities. Each agent is defined by a YAML configuration file.

Each agent integrates with:
- **ADK Runtime**: For AI model access, tool execution, and session management
- **A2A Protocol**: For standardized agent-to-agent communication
- **Tool Registry**: Access to built-in and custom tools
- **Artifact Service**: For file handling and management


For example, an agent configured with SQL database tools can execute queries, perform data analysis, and generate visualizations through the integrated tool ecosystem, all while maintaining conversation context through its session management.

### The Agent Lifecycle

Agents in Solace Agent Mesh follow the A2A protocol lifecycle and interact with the agent registry:

- **Discovery**: Agents start broadcasting discovery messages on startup to announce their availability and capabilities to the agent mesh.

- **Active**: The agent listens for A2A protocol messages on its designated topics and processes incoming tasks through the ADK runtime.

- **Execution**: The agent works on a task. They can also delegate tasks to other agents through the peer-to-peer A2A communication protocol.

- **Cleanup**: When shutting down, agents perform session cleanup and deregister from the agent mesh.


### Potential Agent Examples

- **RAG (Retrieval Augmented Generation) Agent**: An agent that can retrieve information based on a natural language query using an embedding model and vector database, and then generate a response using a language model.

- **External API Bridge**: An agent that acts as a bridge to external APIs, retrieving information from third-party services such as weather APIs or product information databases.

- **Internal System Lookup**: An agent that performs lookups in internal systems, such as a ticket management system or a customer relationship management (CRM) database.

- **Natural Language Processing Agent**: An agent that can perform tasks like sentiment analysis, named entity recognition, or language translation.


## Built-In Tools

Solace Agent Mesh comes with a comprehensive set of built-in tools that agents can use. These tools are automatically available to all agents and provide essential capabilities, and can be added through the agent configuration file.

### Artifact Tools
- **Create Artifact**: Create and manage files with automatic metadata injection
- **Load Artifact**: Retrieve and process existing artifacts
- **Append to Artifact**: Add content to existing files
- **Extract Content**: Extract and analyze content from various file types
- **List Artifacts**: Browse available artifacts in the system

### Data Analysis Tools
- **SQL Query**: Execute SQL queries against databases
- **JQ Transform**: Transform JSON data using JQ expressions
- **Plotly Charts**: Generate interactive charts and visualizations
- **SQLite Database**: Create and query SQLite databases

### Web Tools
- **Web Scraping**: Extract content from web pages
- **HTTP Requests**: Make API calls and web requests

### Communication Tools
- **Peer Agent Tool**: Delegate tasks to other agents in the agent mesh
- **Audio Tools**: Process and analyze audio content
- **Image Tools**: Handle image processing and analysis

## User-Defined Agents

Using Solace Agent Mesh and the SAM CLI, you can create your own agents. Agents are configured through YAML files that specify:

- Agent name and instructions
- LLM model configuration
- Available tools and capabilities
- Artifact and session management settings
- Discovery settings

The following SAM CLI command creates an agent configuration:

```sh
sam add agent my-agent [--gui]
```

For more information, see [Creating Custom Agents](../user-guide/create-agents.md).

## Agent Plugins

You can also use agents built by the community or Solace directly in your app with little to no configuration.

For more information, see [Use a Plugin](./plugins.md#use-a-plugin).

