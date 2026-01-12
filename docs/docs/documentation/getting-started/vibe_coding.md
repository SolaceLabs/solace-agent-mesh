---
title: Vibe Coding
sidebar_position: 20
---

# Vibe Coding

Vibe Coding is an AI-assisted development approach that enables you to quickly create and extend Agent Mesh components—including plugins, agents, gateways, and core functionality—with minimal knowledge of the Solace Agent Mesh codebase. By leveraging Context7's MCP integration, your coding assistant gains deep knowledge of the Solace Agent Mesh codebase and documentation.

## Who Should Use Vibe Coding?

Vibe Coding is ideal for:

- Developers creating Solace Agent Mesh projects with custom agents, plugins, and gateways
- Contributors extending the Solace Agent Mesh repository

## Prerequisites

Before you begin, ensure you have:

- A standard IDE (such as VS Code)
- A coding assistant with MCP support (such as Claude Code). See the [list of supported clients](https://context7.com/docs/resources/all-clients).
- Python V3.10.6 to V3.13
- (Optional) A Context7 API key (free for anyone)

## Installation

### Step 1: Set Up Context7

1. Optionally create a free account at [Context7](https://context7.com) and generate an API key at [context7 dashboard](https://context7.com/dashboard) for higher rate limits.

2. Follow the [MCP installation instructions](https://github.com/upstash/context7?tab=readme-ov-file#%EF%B8%8F-installation) for your IDE to connect your coding assistant to Context7 using the MCP server. Optionally you can use your API key for the integration.

### Step 2: Verify Integration

Ask your coding assistant:

```
Using the `solacelabs/solace-agent-mesh` context7 library when answering questions in this chat session.
```

Review the response from your coding assistant to confirm that it acknowledges the Context7 integration and recognizes the `solacelabs/solace-agent-mesh` library. Depending on the assistant, you might see confirmations such as:  
`I've successfully configured the solacelabs/solace-agent-mesh context7 library ...`  
or  `I'll use the solacelabs/solace-agent-mesh library ...`  
This ensures your coding agent is correctly set up to leverage the Solace Agent Mesh knowledge base.

### Step 3: Setup project environment

1. Ensure that the correct versions of Python (v1.10–v1.13) and [PIP package manager](https://pip.pypa.io/en/stable/installation/) are installed and properly configured.

    Verify python and pip:
    ```
    python --version
    pip --version
    ```

2. Create a new, empty project in your IDE. Although vibe coding works in any workspace, existing files in a project may influence its behavior and results.

## Using Vibe Coding

Once configured, you can interact with your coding assistant through natural language prompts.

:::note
You need to specify the library at least once in your chat session to activate the Context7 integration.
:::

### Example Prompts

**Getting Information About Solace Agent Mesh:**
```
Using `solacelabs/solace-agent-mesh` context7 library, give me a list of built-in tools.
```

**Creating a New Solace Agent Mesh Project:**
```
Using `solacelabs/solace-agent-mesh` context7 library, initialize a Solace Agent Mesh project called example_app.
```

**Creating a New Agent:**
```
Using `solacelabs/solace-agent-mesh` context7 library, create a calculator agent that sums two numbers.
```

**Creating a New Plugin Using Built-in Tools:**
```
Using the `solacelabs/solace-agent-mesh` context7 library and built-in tools, create an image analysis plugin that can generate images and describe images.
```

**Creating a New Gateway:**
```
Using the `solacelabs/solace-agent-mesh` context7 library, create a Discord gateway that enables message exchange with the Discord chat application.
```


To avoid mentioning `solacelabs/solace-agent-mesh` context7 library in every prompt, configure your MCP client with a rule that automatically triggers the library for any code-related request.

```
Claude Code: CLAUDE.md
Or the equivalent configuration in your MCP client.
```

Example rule:
```
Automatically use `solacelabs/solace-agent-mesh` context7 library without requiring me to explicitly request it.
```


## Troubleshooting

Vibe Coding provides an interactive development environment that generates high-quality code. However, the generated code and configurations may occasionally contain bugs. Follow these best practices to resolve issues quickly:

### Best Practices

- **Generate Tests**: After code generation, ask your coding assistant to create comprehensive tests for the generated code.
- **Iterative Debugging**: If you encounter errors during execution, provide the error log to your coding assistant in the same chat session and request a fix.
- **Review Generated Code**: Review the generated code to ensure it meets your requirements and follows best practices.