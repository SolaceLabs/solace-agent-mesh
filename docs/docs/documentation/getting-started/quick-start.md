---
title: Quick Start
sidebar_position: 30
---

# Quick Start

To get started with Solace Agent Mesh, you can either use the preset configuration from the Docker image or create your own complete project.

## Use Preset Agents

### Prerequisites
1. You must have Docker (or Podman) installed.
2. You must have an available AI provider and API key. For best results, use a state-of-the-art AI model like Anthropic Claude Sonnet 4, Google Gemini 2.5 pro, or OpenAI GPT-5.

### Run Preset Agents

You can run pre-made Solace Agent Mesh agents to quickly get started with Solace Agent Mesh without needing to set up a project from scratch. 

```sh
docker run --rm -it -p 8000:8000 --platform linux/amd64  --env-file <your-env-file-path> solace/solace-agent-mesh:latest
```

- Provide the required environment variables. You can also pass them as command-line arguments using the `-e` flag.

Alternatively, you can combine your project with the preset app or only run specific agents from it.

You can find a list of all available preset apps in the [Solace Agent Mesh GitHub repository](https://github.com/SolaceLabs/solace-agent-mesh/tree/main/preset/agents).

:::tip
To run your custom agent without creating a new project, you can use the Docker image as follows:

```bash
docker run --rm -it --platform linux/amd64  -p 8000:8000 -v $(pwd):/app \
  -e LLM_SERVICE_ENDPOINT=<your-llm-endpoint> \
  -e LLM_SERVICE_API_KEY=<your-llm-api-key> \
  -e LLM_SERVICE_PLANNING_MODEL_NAME=<your-llm-planning-model-name> \
  -e LLM_SERVICE_GENERAL_MODEL_NAME=<your-llm-general-model-name> \
  solace/solace-agent-mesh:latest run /preset/agents/basic /app/my-agent
```

- You can update `/app/my-agent` with the path to your agent YAML config. Note: You will still need either a `shared_config.yaml` file or to hard code the settings in your agent configuration.
- `/preset/agents/basic` only runs the required agents, you can use `/preset/agents` to load all agents.
- This example command only has the minimum required environment variables.
:::

## Create a Project

:::note[Plugins]
Looking to get started with plugins? For more information, see the [Plugins](../concepts/plugins.md).
:::

### Prerequisites

1. You must have installed the Solace Agent Mesh CLI. If not, see the [Installation](./installation.md) page.
2. You must have activated the virtual environment you created following the [Installation](./installation.md) page. For containerized deployment such as Docker, ignore this prerequisite.
3. You must have an available AI provider and API key. For best results, use a state-of-the-art AI model like Anthropic Claude Sonnet 4, Google Gemini 2.5 pro, or OpenAI GPT-5.

Create a directory for your project and navigate to it.

```sh
mkdir my-agent-mesh
cd my-agent-mesh
```

Run the `init` command and follow the prompts to create your project.

```sh
solace-agent-mesh init
```
During initialization, you can choose to configure your project directly in the terminal or through a web-based interface launched at `http://127.0.0.1:5002`. You are asked for your preference once you run `solace-agent-mesh init`.

Alternatively, you can use the `--gui` flag to skip the prompt and directly open the web-based configuration interface:

```sh
solace-agent-mesh init --gui
```

<details>
  <summary>Docker Alternative for Initialization</summary>

You can also initialize your Solace Agent Mesh project using the official Docker image. This is helpful if you want to avoid local Python/Solace Agent Mesh CLI installation or prefer a containerized workflow from the start.

```sh
docker run --rm -it -v "$(pwd):/app" --platform linux/amd64  -p 5002:5002 solace/solace-agent-mesh:latest init --gui
```

If the OS architecture on your host is not linux/amd64, you must add --platform linux/amd64 when you run the container.

For Broker Setup, do not select the Broker Type `New local Solace broker container`. This option is incompatible with Docker deployments because the `Download and Run Container` action attempts to download a container image from within the already running container, which causes the operation to fail.

</details>

:::tip[Non-Interactive Mode]
You can run the `init` command in a non-interactive mode by passing `--skip` and all the other configurations as arguments.

To get a list of all the available options, run `solace-agent-mesh init --help`
:::


:::info[Model name format]
<details>
  <summary>Browser-based Configurations</summary>

You need to select the LLM Provider first and supported models are populated under LLM Model Name.

If you're using a non-openai model but hosting it on a custom API that follows the OpenAI standards, like Ollama or LiteLLM, you can select the `OpenAI Compatible Provider`.

</details>

<details >
  <summary>CLI-based Configurations</summary>

You need to explicitly specify the model in the format provider/name. For example, `openai/gpt-4o`.

If you're using a non-openai model but hosting it on a custom API that follows the OpenAI standards, like Ollama or LiteLLM, you can still use the `openai` provider.

For example: `openai/llama-3.3-7b`

</details>

This is the case for all the model names, such as LLMs, image generators, embedding models, etc.
:::

## Running the Project

To run the project, you can use the `run` command to execute all the components in a single, multi-threaded application. It's possible to split the components into separate processes. See the [deployment](../deployment/deploy.md) page for more information.

```sh
solace-agent-mesh run
```

:::tip
Environment variables are loaded from your configuration file (typically a `.env` file at the project root) by default. To use system environment variables instead, use the `-u` or `--system-env` option.
:::

To learn more about the other CLI commands, see the [CLI documentation](../concepts/cli.md).

<details>
  <summary>Docker Alternative for Running the Project</summary>

You can also run your Solace Agent Mesh project using the official Docker image. This is helpful if you want to avoid local Python/Solace Agent Mesh CLI installation or prefer a containerized workflow from the start.

```sh
docker run --rm -it -v "$(pwd):/app" --platform linux/amd64  -p 8000:8000 solace/solace-agent-mesh:latest run
```

If your host system architecture is not `linux/amd64`, add the `--platform linux/amd64` flag when you run the container.

:::info[Required Configurations]
For deployments that use the official Docker image, ensure the following:
- Do not use a local Solace broker container.
- Set the environment variables `FASTAPI_HOST="0.0.0.0"` in your `.env` file or system environment variables. This is necessary to expose the FastAPI server to the host machine. 
:::

:::warning
If you are using third-party Python packages or Solace Agent Mesh plugins, you need to build a custom Docker image off the official image and install the required packages there, and then run that custom image instead.

```Dockerfile
FROM solace/solace-agent-mesh:latest
# Option 1: Install a specific package
RUN python3.11 -m pip install --no-cache-dir <your-package>
# Option 2: use a requirements.txt file
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["solace-agent-mesh"]
```

Then build and run your custom image:

```sh
docker build --platform linux/amd64 -t my-custom-image .
docker run --rm -it -v "$(pwd):/app" --platform linux/amd64  -p 8000:8000 my-custom-image run
```
:::
</details>

## Interacting with Solace Agent Mesh

You can use different gateway interfaces to communicate with the system such as REST, Web UI, Slack, MS Teams, and so on. To keep it simple for this demo, we use the browser UI.

To access the browser UI, navigate to `http://localhost:8000` in your web browser. If you specified a different port during the init step, use that port instead. For Docker deployments with custom port mappings (using the `-p` flag), use the host port specified in your port mapping configuration.

Try some commands like `Suggest some good outdoor activities in London given the season and current weather conditions.`.


## Try a Tutorial

Try adding a new agent to the system by following the tutorial on adding an [SQL database agent](../tutorials/sql-database.md). This tutorial guides you through the process of adding the SQL agent plugin and adding some sample data to the database.

## Next Steps

Solace Agent Mesh uses two main types of components, **agents** and **gateways**. The system comes with a built-in orchestrator agent and a web user interface gateway (which you enabled during the `init` step).

You can learn more about [gateways](../concepts/gateways.md). Alternatively, you can learn about [using plugins](../concepts/plugins.md#use-a-plugin) or [creating your own new gateways](../user-guide/create-gateways.md).

Also, you can learn more about [agents](../concepts/agents.md) or about [creating your own agents](../user-guide/create-agents.md).
