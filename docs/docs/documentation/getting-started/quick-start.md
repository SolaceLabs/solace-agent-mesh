---
title: Quick Start
sidebar_position: 30
---

# Quick Start

:::note[Plugins]
Looking to get started with plugins? For more information, see the [Plugins](../concepts/plugins/index.md).
:::

To get started with Solace Agent Mesh, you must first create a project.

## Prerequisites

1. You have installed the Solace Agent Mesh CLI. If not, see the [Installation](./installation.md) page.
2. You have an available AI provider and API key. For best results, use a state-of-the-art AI model like Anthropic Claude Sonnet 3.7 or OpenAI GPT-4o.

## Create a Project

Ensure you have the Solace Agent Mesh (SAM) CLI (run `solace-agent-mesh --version` or `sam `) available. If not, see [Installation](./installation.md).

Create a directory for your project and navigate to it.

```sh
mkdir my-agent-mesh
cd my-agent-mesh
```

Run the `init` command and follow the prompts to create your project.

```sh
solace-agent-mesh init
```

:::tip[Non-Interactive Mode]
You can run the `init` command in a non-interactive mode by passing `--skip` and all the other configurations as arguments.

To get a list of all the available options, run `solace-agent-mesh init --help`
:::

:::info[Model name format]
When passing the model names, you need to use the format `provider/name` where provider is the provider API interface definition name for example `openai` if the model is using the standard OpenAI API interface and `name` is the model name like `gpt-4o`.

If you're using a non-openai model but hosting it on a custom API that follows the OpenAI standards, like Ollama or LiteLLM, you can still use the `openai` provider.

For example: `openai/llama-3.3-7b`

This is the case for all the model names, such as LLMs, image generators, embedding models, etc.
:::

Your project configurations have been written to the `solace-agent-mesh.yaml` file. To learn more about this file and its configurations, see the [configurations](./configuration.md) page.

## Building the Project

The build command generates all the respective [solace-ai-connector](../user-guide/solace-ai-connector.md) configuration files. Solace AI Event Connector is the underlying library that runs all the components and connects Solace Agent Mesh to a Solace PubSub+ event broker.

To build the project, run the following command:

```sh
solace-agent-mesh build
```

:::warning
You must run the `solace-agent-mesh` commands at the root directory of your project where the `solace-agent-mesh.yaml` file is located.
:::

## Running the Project

To run the project, you can use the `run` command to execute all the components in a single, multi-threaded application. It's possible to split the components into separate processes. See the [deployment](../deployment/deploy.md) page for more information.

```sh
solace-agent-mesh run -e
```

:::tip
You can use `-e` flag to load the local `.env` file when running the project.
:::

:::tip
You can combine the build and run steps by using `solace-agent-mesh run -eb`.
:::

To learn more about the other CLI commands, see the [CLI documentation](../concepts/cli.md).

## Interacting with SAM

You can use different gateway interfaces to communicate with the system such as REST, Web UI, Slack, MS Teams, etc. To keep it simple for this demo, we will use the browser UI. To connect to the browser UI, open a browser and navigate to `http://127.0.0.1:5001`. If you chose another port during the `init` step, use that port instead.

This will provide a simple chat interface where you can interact with the Agent Mesh. Try some commands like `Suggest some good outdoor activities in London given the season and current weather conditions.` or `Generate a mermaid diagram of the OAuth login flow`.

## Sending a Request via REST API

You can also interact with SAM via a **REST API**.

The REST API gateway runs on `http://localhost:5050` by default. You can send a **POST** request to the `/api/v1/request`.

For example, send a request using `curl`:

```sh
curl --location 'http://localhost:5050/api/v1/request' \
--header 'Authorization: Bearer None' \
--form 'prompt="Suggest some good outdoor activities in London given the season and current weather conditions."' \
--form 'stream="false"'
```

:::warning
It might take a while for the system to respond. See the [observability](../deployment/observability.md) page for more information about monitoring the system while it's processing the request.
:::

Sample output:

```json
{
  "created": 1797746509,
  "id": "restapi-81c30d2c-4943-449a-8d4c-65d0f86ee70a",
  "response": {
    "content": "Outdoor Activities in London: Spring Edition. Today's Perfect Activities (13°C, Light Cloud): - Royal Parks Exploration : Hyde Park and Kensington Gardens...",
    "files": []
  },
  "session_id": "c4d46aec-78d6-4a82-9c92-bcf4546f6f84"
}
```

:::info
Files would be returned as base64-encoded strings, with the following structure:

```json
"files": [
  {
    "name": "diagram.png",
    "content": "base64 encoded string",
    "mime_type":"image/png"
  }
]
```

For example, here's a prompt to retrieve a file: `prompt="Give me a random bar chart"`
:::

## Try a Tutorial

Try adding a new agent to the system by following the tutorial on adding an [SQL database agent](../tutorials/sql-database.md). This tutorial guides you through the process of adding the SQL agent plugin and adding some sample data to the database.

## Next Steps

Solace Agent Mesh requires two types of components, **agents** and **gateways**. The system comes with a set of built-in agents and a REST API gateway (which you enabled during the `init` step) include a browser UI running on top of it.

You can learn more about [gateways](../concepts/gateways.md). Alternatively, you can learn about [adding a pre-built gateway interfaces](../concepts/gateways.md#gateway-from-interfaces) or [creating your own new gateways](../user-guide/custom-gateways.md).

Also, you can learn more about [agents](../concepts/agents.md) or about [creating your own agents](../user-guide/custom-agents.md).

:::note
If you said no to the REST API gateway during the `init` step, you can add it after using the following command:

```sh
solace-agent-mesh add gateway my-rest-endpoint --interface rest-api
```

:::
