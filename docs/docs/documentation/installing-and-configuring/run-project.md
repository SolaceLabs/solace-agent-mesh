---
title: Creating and Running an Agent Mesh Project
sidebar_position: 320
---

This guide walks you through creating and running a complete Agent Mesh project. This approach provides full control over your configuration and is suitable for development, testing, and production environments.

:::note[Plugins]
Looking to get started with plugins? For more information, see [Plugins](../components/plugins.md).
:::

## Prerequisites

Before you begin, ensure you have the following:

1. **Agent Mesh CLI installed** - If not installed, see the [installation guide](installation.md)
2. **Virtual environment activated** - You must have activated the virtual environment you created during installation (not required for containerized deployments)
3. **AI provider and API key** - For best results, use a state-of-the-art AI model like Anthropic Claude Sonnet 4, Google Gemini 2.5 Pro, or OpenAI GPT-4

## Create Your Project

### Step 1: Set Up Project Directory

Create a directory for your project and navigate to it:

```sh
mkdir my-agent-mesh
cd my-agent-mesh
```

### Step 2: Initialize the Project

Run the [`init`](../components/cli.md) command and follow the prompts to create your project:

```sh
solace-agent-mesh init
```

During initialization, you can choose to configure your project directly in the terminal or through a web-based interface launched at `http://127.0.0.1:5002`. You are asked for your preference when you run [`solace-agent-mesh init`](../components/cli.md).

#### Web-Based Configuration

To skip the prompt and directly open the web-based configuration interface, use the `--gui` flag:

```sh
solace-agent-mesh init --gui
```

The web-based interface provides an intuitive way to configure your project settings, including:
- AI model selection and configuration
- Solace event broker setup
- Gateway configuration
- Environment variable management

#### Command-Line Configuration

For automated setups or when you prefer command-line interaction, you can run the [`init`](../components/cli.md) command in non-interactive mode by passing `--skip` and all other configurations as arguments.

To get a list of all available options, run:

```sh
solace-agent-mesh init --help
```

### Step 3: Configure AI Models

Understanding the model name format is important for proper configuration:

#### Web-Based Configuration
When using the web interface:
1. Select the LLM Provider first
2. Supported models are populated under LLM Model Name
3. If you're using a non-OpenAI model hosted on a custom API that follows OpenAI standards (like Ollama or LiteLLM), select the `OpenAI Compatible Provider`

#### Command-Line Configuration
When using the CLI, you must explicitly specify the model in the format `provider/name`. For example:
- `openai/gpt-4o`
- `anthropic/claude-3-sonnet-20240229`

If you're using a non-OpenAI model hosted on a custom API that follows OpenAI standards, you can still use the `openai` provider. For example: `openai/llama-3.3-7b`

This format applies to all model types, including LLMs, image generators, and embedding models.

### Docker Alternative for Initialization

You can also initialize your Agent Mesh project using the official Docker image. This approach is helpful if you want to avoid local Python/Agent Mesh CLI installation or prefer a containerized workflow.

```sh
docker run --rm -it -v "$(pwd):/app" --platform linux/amd64 -p 5002:5002 solace/solace-agent-mesh:latest init --gui
```

**Important Considerations for Docker Initialization**:
- If your host OS architecture is not `linux/amd64`, you must add `--platform linux/amd64` when you run the container
- For Broker Setup, do not select the Broker Type `New local Solace broker container`. This option is incompatible with Docker deployments because the `Download and Run Container` action attempts to download a container image from within the already running container, which causes the operation to fail

## Running Your Project

### Local Execution

To run the project locally, use the [`run`](../components/cli.md) command to execute all components in a single, multi-threaded application:

```sh
solace-agent-mesh run
```

This command starts all configured agents and gateways, creating a complete agent mesh system.

**Environment Variables**: By default, environment variables are loaded from your configuration file (typically a `.env` file at the project root). To use system environment variables instead, use the `-u` or `--system-env` option.

**Component Separation**: While the [`run`](../components/cli.md) command executes all components together, it's possible to split components into separate processes. See the [deployment guide](../deploying/deploying.md) for more information about advanced deployment options.

### Docker Execution

You can also run your Agent Mesh project using the official Docker image:

```sh
docker run --rm -it -v "$(pwd):/app" --platform linux/amd64 -p 8000:8000 solace/solace-agent-mesh:latest run
```

**Platform Compatibility**: If your host system architecture is not `linux/amd64`, add the `--platform linux/amd64` flag when you run the container.

#### Docker Configuration Requirements

For deployments that use the official Docker image, ensure the following:
- **Do not use a local Solace event broker container** - This configuration is incompatible with Docker deployments
- **Set `FASTAPI_HOST="0.0.0.0"`** in your `.env` file or system environment variables. This setting is necessary to expose the FastAPI server to the host machine

#### Using Custom Dependencies with Docker

If you are using third-party Python packages or Agent Mesh plugins, you need to build a custom Docker image based on the official image:

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
docker run --rm -it -v "$(pwd):/app" --platform linux/amd64 -p 8000:8000 my-custom-image run
```

## Interacting with Your Agent Mesh

Agent Mesh supports multiple gateway interfaces for communication, including REST, Web UI, Slack, MS Teams, and more. The web interface provides the most straightforward way to get started.

### Accessing the Web Interface

1. **Navigate to the Interface**: Open `http://localhost:8000` in your web browser
2. **Custom Ports**: If you specified a different port during initialization, use that port instead
3. **Docker Port Mappings**: For Docker deployments with custom port mappings (using the `-p` flag), use the host port specified in your port mapping configuration

### Testing Your Setup

Try some example commands to verify your agent mesh is working correctly:
- "Suggest some good outdoor activities in London given the season and current weather conditions"
- "Help me plan a project timeline for a software development project"
- "Analyze the latest trends in artificial intelligence"

## Understanding Your System

Your Agent Mesh project consists of two main types of components:

### Agents
AI-powered components that perform specific tasks and can communicate with each other. Your system includes:
- **Built-in orchestrator agent**: Coordinates tasks and manages communication between other agents
- **Custom agents**: Any additional agents you configure for specific domains or tasks

### Gateways
Interface components that allow external systems and users to interact with the agent mesh:
- **Web user interface gateway**: Provides the browser-based interface you enabled during initialization
- **Additional gateways**: REST APIs, Slack integrations, or other interfaces you configure

## Next Steps

Now that you have a working Agent Mesh project, you can:

### Extend Your System
- **Add new agents**: Learn about [creating your own agents](../developing/create-agents.md) for specific domains
- **Configure additional gateways**: Explore [creating new gateways](../developing/create-gateways.md) for different interfaces
- **Use plugins**: Discover how to [use existing plugins](../components/plugins.md#use-a-plugin) to extend functionality

### Learn More
- **Understand agents**: Deep dive into [how agents work](../components/agents.md)
- **Explore gateways**: Learn more about [gateway types and configuration](../components/gateways.md)
- **CLI commands**: Discover additional [CLI capabilities](../components/cli.md)

### Try Tutorials
- **SQL Database Integration**: Follow the tutorial on adding an [SQL database agent](../developing/tutorials/sql-database.md)
- **Custom Integrations**: Explore other integration tutorials in the user guide

To learn more about CLI commands and advanced configuration options, see the [CLI documentation](../components/cli.md).