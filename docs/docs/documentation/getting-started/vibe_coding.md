---
title: Vibe Coding
sidebar_position: 20
---

# Vibe Coding

Vibe Coding is an AI-assisted development approach that enables you to quickly create and extend Agent Mesh components—including plugins, agents, gateways, and core functionality—with minimal knowledge of the SAM codebase. By leveraging Context7's MCP integration, your coding assistant gains deep knowledge of the SAM codebase and documentation.

## Who Should Use Vibe Coding?

Vibe Coding is ideal for:

- Developers creating SAM projects with custom agents, plugins, and gateways
- Contributors extending the SAM repository

## Prerequisites

Before you begin, ensure you have:

- A standard IDE (such as VS Code)
- A Context7 API key (free for anyone)
- A coding assistant with MCP support (such as GitHub Copilot, Cursor, or Cline)

## Installation

### Step 1: Set Up Context7

1. Create a free account at [Context7](https://context7.com) and generate an API key.

2. Follow the [MCP installation instructions](https://github.com/upstash/context7?tab=readme-ov-file#%EF%B8%8F-installation) for your IDE to connect your coding assistant to Context7 using the MCP server. You'll need your API key for this integration.

### Step 2: Verify Integration

Test your setup by asking your coding assistant:

```
Using solacelabs/solace-agent-mesh library, tell me a description of the Solace Agent Mesh project.
```

If the integration is not properly configured, the coding agent does not connect to Context7 MCP.

## Using Vibe Coding

Once configured, you can interact with your coding assistant through natural language prompts.

:::note
You need to specify the library at least once in your chat session to activate the Context7 integration.
:::

### Example Prompts

**Getting Information About SAM:**
```
Using solacelabs/solace-agent-mesh library, give me the broker configurations with possible data fields.
```

**Creating a New SAM Project:**
```
Using /solace/solace-agent-mesh library, initialize a SAM project called example_app.
```

**Creating a New Plugin:**
```
Using solacelabs/solace-agent-mesh library, create a calculator plugin that sums two numbers.
```

## Troubleshooting

Vibe Coding provides an interactive development environment that generates high-quality code. However, the generated code and configurations may occasionally contain bugs. Follow these best practices to resolve issues quickly:

### Best Practices

- **Generate Tests**: After code generation, ask your coding assistant to create comprehensive tests for the generated code.
- **Iterative Debugging**: If you encounter errors during execution, provide the error log to your coding assistant in the same chat session and request a fix.
- **Review Generated Code**: Review the generated code to ensure it meets your requirements and follows best practices.