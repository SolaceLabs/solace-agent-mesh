---
title: MCP Integration
sidebar_position: 20
---

# MCP Integration

In this tutorial, we will walk you through the process of integrating a Model Context Protocol (MCP) Server into Solace Agent Mesh.

:::info[Learn about agents and plugins]
You should have an understanding of agents and plugins in the Solace Agent Mesh. For more information, see [Agents](../concepts/agents.md) and [Using Plugins](../concepts/plugins/use-plugins.md).
:::

As an example, you are going to integrate the [MCP server-filesystem Server](https://www.npmjs.com/package/@modelcontextprotocol/server-filesystem) into the Solace Agent Mesh Framework to perform simple filesystem commands.

## Setting Up the Environment

You must [install Solace Agent Mesh and Solace Mesh Agent (SAM) CLI](../getting-started/installation.md), and then you'll want to [create a new Solace Agent Mesh project](../getting-started/quick-start.md).

This project also requires the installation of Node.js and the NPM package manager.

## Creating the `sam-mcp-server` Plugin

You will be using the `sam-mcp-server` plugin from the [solace-agent-mesh-core-plugins](https://github.com/SolaceLabs/solace-agent-mesh-core-plugins) repo for this tutorial. This plugin creates an agent that communicates with the MCP Server.

Once you have your project set up, you can add the `sam_mcp_server` plugin to the project using the following command:

```sh
solace-agent-mesh plugin add sam_mcp_server --pip -u git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-mcp-server
```

This plugin requires two environment variables to be set:

- `MCP_SERVER_NAME`: The name of the MCP Server
- `MCP_SERVER_COMMAND`: The command used to run the MCP Server

To use the `fileserver` MCP Server, update your `.env` file with the following values:

```sh
MCP_SERVER_NAME=filesystem
MCP_SERVER_COMMAND=npx -y @modelcontextprotocol/server-filesystem ${HOME}/sandbox
```

The `MCP_SERVER_COMMAND` runs the `filesystem` MCP Server and allows it to manage files in the `${HOME}/sandbox` directory.

Next, create the sandbox directory and create a file:

```sh
mkdir ${HOME}/sandbox
touch ${HOME}/sandbox/my_file
```

Finally, add `mcp_server` to the plugin agents list in the `solace-agent-mesh.yaml` file:

```yaml
...
  plugins:

  ...

  - name: sam_mcp_server
    load_unspecified_files: false
    includes_gateway_interface: true
    load:
      agents:
        - mcp_server
      gateways: []
      overwrites: []

   ...
```

Now, you can build and run the plugin:

```sh
sam run -be
```

For more information, see [Solace Agent Mesh CLI](../concepts/cli.md).

## Testing the Plugin

First, you must retrieve a list of the files from the filesystem.

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
