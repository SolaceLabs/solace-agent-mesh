---
title: Try Agent Mesh
sidebar_position: 16
---

# Try Agent Mesh

Get started quickly with Agent Mesh using our pre-configured Docker image. This approach lets you explore the capabilities of Agent Mesh without setting up a complete project.

:::warning
This setup uses in-memory queues instead of a real Solace event broker, making it suitable only for experimentation and small-scale development. It is not suitable for production environments, large projects, or CI/CD pipelines.
:::

## Prerequisites

Before you begin, ensure you have:

* Docker (or Podman) installed on your system
* An AI provider and API key from any major provider. For best results, use a state-of-the-art AI model like Anthropic Claude Sonnet 4, Google Gemini 2.5 Pro, or OpenAI GPT-4

:::tip Ready for Development?
If you're ready to set up a full development environment with complete project control, skip this quick trial and go directly to the [installation guide](../installing-and-configuring/installation.md) followed by the [project setup guide](../installing-and-configuring/run-project.md).
:::

## Run the Docker Image

The simplest way to try Agent Mesh is to run the pre-configured agents that come with the Docker image. This approach gets you up and running immediately without any project setup.

```sh
docker run --rm -it -p 8000:8000 --platform linux/amd64 --env-file <your-env-file-path> solace/solace-agent-mesh:latest
```

You can provide the required environment variables using an environment file as shown above, or pass them directly as command-line arguments using the `-e` flag, as shown in the section that follows. The preset configuration includes several ready-to-use agents that demonstrate the capabilities of Agent Mesh. You can find a complete list of all available preset agents in the [Agent Mesh GitHub repository](https://github.com/SolaceLabs/solace-agent-mesh/tree/main/preset/agents).

If your host system architecture is not `linux/amd64`, you must add the `--platform linux/amd64` flag when you run the container.

### Using Custom Agents (Optional)

Although the preset agents are sufficient for exploring the capabilities of Agent Mesh, you can optionally run your own custom agents if you already have them configured. However, for any serious development work, we recommend following the complete [project setup guide](../installing-and-configuring/run-project.md) instead of this Docker shortcut.

If you do want to test a custom agent quickly, you can mount your agent configuration into the container using the following command:

```bash
docker run --rm -it --platform linux/amd64 -p 8000:8000 -v $(pwd):/app \
  -e LLM_SERVICE_ENDPOINT=<your-llm-endpoint> \
  -e LLM_SERVICE_API_KEY=<your-llm-api-key> \
  -e LLM_SERVICE_PLANNING_MODEL_NAME=<your-llm-planning-model-name> \
  -e LLM_SERVICE_GENERAL_MODEL_NAME=<your-llm-general-model-name> \
  solace/solace-agent-mesh:latest run /preset/agents/basic /app/my-agent
```

Replace `/app/my-agent` with the path to your agent YAML configuration file. Note that you still need either a `shared_config.yaml` file or hard-coded settings in your agent configuration. The `/preset/agents/basic` path runs only the required agents, while `/preset/agents` loads all available agents. This example includes only the minimum required environment variables.

## Explore the Web Interface

After the Docker container starts successfully, you can interact with Agent Mesh through the web interface. Navigate to `http://localhost:8000` in your web browser and try commands like "Suggest some good outdoor activities in London given the season and current weather conditions."

The web interface provides an intuitive way to interact with your agents and explore the capabilities of Agent Mesh without any additional setup.

## Next Steps

Once you've explored the basic functionality, you can learn more about [agents](../components/agents.md) and how they work, explore [gateways](../components/gateways.md) and different interface options, or try [using plugins](../components/plugins.md#use-a-plugin) to extend functionality.

For serious development work, set up a complete project by following the [installation guide](../installing-and-configuring/installation.md) and then the [project setup guide](../installing-and-configuring/run-project.md), which provides full control over your configuration and is suitable for development, testing, and production environments.