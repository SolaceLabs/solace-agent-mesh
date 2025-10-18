---
title: Agents
sidebar_position: 220
---

Agents are specialized processing units within the Agent Mesh framework that are built around the Google Agent Development Kit (ADK) and provide the core intelligence layer. They:

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

Agents in Agent Mesh are built around the Solace AI Connector (SAC) component with ADK. Agent Mesh agents are complete self-contained units that can carry out specific tasks or provide domain-specific knowledge or capabilities. Each agent is defined by a YAML configuration file.

Each agent integrates with:
- **ADK Runtime**: For AI model access, tool execution, and session management
- **A2A Protocol**: For standardized agent-to-agent communication
- **Tool Registry**: Access to built-in and custom tools
- **Artifact Service**: For file handling and management


For example, an agent configured with SQL database tools can execute queries, perform data analysis, and generate visualizations through the integrated tool ecosystem, all while maintaining conversation context through its session management.

### The Agent Lifecycle

Agents in Agent Mesh follow the A2A protocol lifecycle and interact with the agent registry:

- **Discovery**: Agents start broadcasting discovery messages on startup to announce their availability and capabilities to the agent mesh.

- **Active**: The agent listens for A2A protocol messages on its designated topics and processes incoming tasks through the ADK runtime.

- **Execution**: The agent works on a task. They can also delegate tasks to other agents through the peer-to-peer A2A communication protocol.

- **Cleanup**: When shutting down, agents perform session cleanup and deregister from the agent mesh.


### Potential Agent Examples

- **RAG (Retrieval Augmented Generation) Agent**: An agent that can retrieve information based on a natural language query using an embedding model and vector database, and then generate a response using a language model.

- **External API Bridge**: An agent that acts as a bridge to external APIs, retrieving information from third-party services such as weather APIs or product information databases.

- **Internal System Lookup**: An agent that performs lookups in internal systems, such as a ticket management system or a customer relationship management (CRM) database.

- **Natural Language Processing Agent**: An agent that can perform tasks like sentiment analysis, named entity recognition, or language translation.


## Tool Ecosystem

Agents perform tasks by using **tools**. A tool is a specific capability, like querying a database, calling an external API, or generating an image. The Agent Mesh framework provides a flexible and powerful tool ecosystem, allowing you to equip your agents with the right capabilities for any job.

There are three primary ways to add tools to an agent:

### 1. Built-in Tools

Agent Mesh includes a rich library of pre-packaged tools for common tasks like data analysis, file management, and web requests. These are the easiest to use and can be enabled with just a few lines of configuration.

-   **Use Case**: For standard, out-of-the-box functionality.
-   **Learn More**: See the [Built-in Tools Reference](./builtin-tools/builtin-tools.md) for a complete list and configuration details.

### 2. Custom Python Tools

For unique business logic or specialized tasks, you can create your own tools using Python. This is the most powerful and flexible method, supporting everything from simple functions to advanced, class-based tool factories that can generate multiple tools programmatically.

-   **Use Case**: For implementing custom logic, integrating with proprietary systems, or creating dynamically configured tools.
-   **Learn More**: See the [Creating Python Tools](../developing/creating-python-tools.md) guide for a complete walkthrough.

### 3. MCP (Model Context Protocol) Tools

For integrating with external, standalone tool servers that conform to the Model Context Protocol, you can configure an MCP tool. This allows agents to communicate with tools running in separate processes or on different machines.

-   **Use Case**: For integrating with existing MCP-compliant tool servers or language-agnostic tool development.
-   **Learn More**: See the [MCP Integration Tutorial](../developing/tutorials/mcp-integration.md).

## Agent Card

The Agent Card is a public-facing profile that describes an agent's identity, capabilities, and how to interact with it. It functions like a digital business card, allowing other agents and clients within Agent Mesh to discover what an agent can do. This information is published by the agent and is crucial for dynamic discovery and interoperability.

The Agent Card is defined in the agent's YAML configuration file under the `agent_card` section.

### Key Fields

You can configure the following fields in the `agent card`:

-   **`description`**: A summary of the agent's purpose and capabilities.
-   **`defaultInputModes`**: A list of supported MIME types for input (e.g., `["text/plain", "application/json", "file"]`).
-   **`defaultOutputModes`**: A list of supported MIME types for output.
-   **`skills`**: A list of specific skills the agent possesses. Each skill corresponds to a capability, often backed by a tool.

### Skills

A skill describes a specific function the agent can perform. It provides granular detail about the agent's abilities.

Key attributes of a skill include:

-   **`id`**: A unique identifier for the skill, which should match the `tool_name` if the skill is directly mapped to a tool.
-   **`name`**: A human-readable name for the skill.
-   **`description`**: A clear explanation of what the skill does, which helps the LLM (and other agents) decide when to use it.

### Example Configuration

Here is an example of an `agent_card` configuration for a "Mermaid Diagram Generator" agent:

```yaml
# ... inside app_config ...
agent_card:
  description: "An agent that generates PNG images from Mermaid diagram syntax."
  defaultInputModes: ["text"] # Expects Mermaid syntax as text
  defaultOutputModes: ["text", "file"] # Confirms with text, outputs file artifact
  skills:
  - id: "mermaid_diagram_generator"
    name: "Mermaid Diagram Generator"
    description: "Generates a PNG image from Mermaid diagram syntax. Input: mermaid_syntax (string), output_filename (string, optional)."
```

This card clearly communicates that the agent can take text (the Mermaid syntax) and produce a file (the PNG image), and it details the specific "mermaid_diagram_generator" skill it offers. For more details on creating agents and configuring their cards, see [Creating Custom Agents](../developing/create-agents.md).

## User-Defined Agents

Using the Agent Mesh CLI, you can create your own agents. Agents are configured through YAML files that specify:

- Agent name and instructions
- LLM model configuration
- Available tools and capabilities
- Artifact and session management settings
- Discovery settings

The following Agent Mesh CLI command creates an agent configuration:

```sh
sam add agent my-agent [--gui]
```

For more information, see [Creating Custom Agents](../developing/create-agents.md).

## Remote A2A Agents

In addition to agents that run natively within Agent Mesh, you can integrate external agents that communicate using the A2A protocol over HTTPS. These remote agents run on separate infrastructure but can still participate in collaborative workflows with mesh agents.

Remote A2A agents are useful when you need to:

- Integrate third-party agents from vendors or partners
- Connect agents running in different cloud environments or on-premises systems
- Maintain service isolation while enabling collaboration
- Gradually migrate existing A2A agents to the mesh

To integrate external agents, you use a proxy component that acts as a protocol bridge between A2A over HTTPS and A2A over Solace event mesh. The proxy handles authentication, artifact flow, and discovery, making remote agents appear as native mesh agents to other components.

For detailed information on configuring and deploying proxies for remote agents, see [Proxies](./proxies.md).

## Agent Plugins

You can also use agents built by the community or Solace directly in your app with little to no configuration.

For more information, see [Use a Plugin](./plugins.md#use-a-plugin).

