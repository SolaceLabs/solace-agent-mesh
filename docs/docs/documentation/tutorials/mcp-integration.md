---
title: MCP Integration
sidebar_position: 20
---

# MCP Integration

In this tutorial, we will walk you through the process of integrating a Model Context Protocol (MCP) Server into Solace Agent Mesh.

:::info[Learn about agents and plugins]
You should have an understanding of agents and plugins in the Solace Agent Mesh. For more information, see [Agents](../concepts/agents.md) and [Using Plugins](../concepts/plugins/use-plugins.md).
:::

This plugin adds capabilities to Solace Agent Mesh (SAM) for interacting with servers that implement the Model Context Protocol (MCP). It provides:

- An Agent (mcp_server): Allows SAM to act as an MCP client, connecting to an external MCP server (like server-filesystem or server-everything) and exposing its tools, resources, and prompts as SAM actions.
- A Gateway Interface: Allows SAM itself to act as an MCP server, exposing its own agents and capabilities to external MCP clients (This part might be less commonly used but is included in the plugin structure).

For this tutorial we'll add the the [Filesystem MCP Server](https://www.npmjs.com/package/@modelcontextprotocol/server-filesystem) as an agent into the Solace Agent Mesh Framework to perform simple filesystem commands.

## Prerequisites

Before starting this tutorial, ensure that you have installed and configured Solace Agent Mesh:

- [Installed Solace Agent Mesh and the SAM CLI](../getting-started/installation.md)
- [Created a new Solace Agent Mesh project](../getting-started/quick-start.md)

In addtion, you will also need to have Node.js and the NPM package manager.

## Step 1: Add the `sam-mcp-server` Plugin

You will be using the `sam-mcp-server` plugin from the [solace-agent-mesh-core-plugins](https://github.com/SolaceLabs/solace-agent-mesh-core-plugins) repository for this tutorial. This plugin creates an agent that communicates with the MCP Server.

Add the plugin to your project using the following command:

```sh
solace-agent-mesh plugin add sam_mcp_server --pip -u git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-mcp-server
```

---

## Step 2: Create an MCP Agent

Next, create an agent instance based on the MCP server template. In this example, we'll call the agent `filesystem_docs`. You can choose any name you want.

```sh
solace-agent-mesh add agent filesystem_docs --copy-from sam_mcp_server:mcp_server
```

This command generates a new configuration file under `configs/agents/filesystem_docs.yaml`. The agent name is automatically substituted through the `config` file.

---

## Step 3: Configure Environment Variables

To configure the plugin, set the appropriate environment variables for your agent.

Since we named the agent `filesystem_docs`, you must set the following environment variables:

- `FILESYSTEM_DOCS_SERVER_DESCRIPTION`: A description of the MCP Server.
- `FILESYSTEM_DOCS_SERVER_COMMAND`: The command used to run the MCP Server.

<details>
    <summary>What if I used a different name for my agent?</summary>

If you chose another name, ensure you prefix your environment variables accordingly. You can always check the correct variable names in the agent's config file (`configs/agents/your_agent_name.yaml`).
</details>

Now update your `.env` file with the following values:

```sh
FILESYSTEM_DOCS_SERVER_COMMAND="npx -y @modelcontextprotocol/server-filesystem ${HOME}/sandbox"
FILESYSTEM_DOCS_SERVER_DESCRIPTION="Provides access to project sandbox files via MCP."
```

This command starts the `filesystem` MCP Server and allows it to manage files in the `${HOME}/sandbox` directory.

Then, create the sandbox directory and a sample file:

```sh
mkdir ${HOME}/sandbox
touch ${HOME}/sandbox/my_file
```

---

## Step 4: Run the Agent

Now, you can build and run the plugin:

```sh
sam run -b
```

This will launch all active agents, including your new `filesystem_docs` MCP agent.

For more information, see [Solace Agent Mesh CLI](../concepts/cli.md).


## Testing the Plugin

First, let's retrieve a list of the files from the filesystem.

```sh
curl --location 'http://localhost:5050/api/v1/request' \
--header 'Authorization: Bearer None' \
--form 'prompt="List the files on the filesystem."' \
--form 'stream="false"'
```

The response includes the file you created in a previous step as expected:

````json
{
  "created": 1739378715,
  "id": "restapi-3570a20d-d4a8-4780-946b-5e1ea3b11ee4",
  "response": {
    "content": "Here are the files in the allowed directory:\n```text\n[FILE] my_file\n```",
    "files": []
  },
  "session_id": "3dbd8425-2962-45e1-be2a-ec7f2cd4a09c"
}
````

Next, create a simple JSON file.

```sh
curl --location 'http://localhost:5050/api/v1/request' \
--header 'Authorization: Bearer None' \
--form 'prompt="Create a json file with two mock employees in the allowed directory of the filesystem."' \
--form 'stream="false"'
```

You will get the following response indicating the requested file was created:

```json
{
  "created": 1739379547,
  "id": "restapi-864e38b0-ebb6-4dcd-85ec-1e325dcbfb00",
  "response": {
    "content": "OK. I have created a json file with two mock employees in the allowed directory of the filesystem. The file is located at `/Users/myuserid/sandbox/employees.json`.",
    "files": []
  },
  "session_id": "e6580943-9a55-4787-a9ca-2bb839725933"
}
```

To verify that the file exists, run the following command:

```sh
cat ${HOME}/sandbox/employees.json
```

You should see the data for the two mock employees in the JSON file:

```json
[
  {
    "firstName": "John",
    "lastName": "Doe",
    "employeeId": 1
  },
  {
    "firstName": "Jane",
    "lastName": "Smith",
    "employeeId": 2
  }
]
```
