---
title: Building Custom Agent Images
sidebar_position: 25
---

# Building Custom Agent Images

This tutorial walks you through packaging a custom agent plugin into a Docker/OCI image suitable for Kubernetes deployment. By the end you will have a container image that extends the SAM Enterprise base image with your own Python tool, ready to deploy with Helm. For the deployment step, see [Agent and Workflow Deployment](https://solaceproducts.github.io/solace-agent-mesh-helm-quickstart/docs/standalone-agent-deployment).

## Prerequisites

You need Docker or Podman installed on your build machine, access to a container registry that your Kubernetes cluster can pull from, and a SAM Enterprise base image. Familiarity with Python packaging basics is helpful but not required---this tutorial covers everything you need. For background on tool function patterns, see [Creating Python Tools](../creating-python-tools.md). For plugin packaging basics, see [Plugins](../../components/plugins.md).

## Step 1: Create the Plugin

Start by setting up a standard Python package for your custom tool. The directory structure follows the `src` layout convention:

```
custom-echo-agent/
├── pyproject.toml
└── src/
    └── custom_echo_agent/
        ├── __init__.py
        └── tools.py
```

The `pyproject.toml` declares the package metadata and uses `hatchling` as the build backend. The `src-path` setting tells Hatch where to find the package source, and the `packages` list ensures only your plugin code is included in the wheel:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "custom_echo_agent"
version = "0.1.0"
description = "A custom echo tool for SAM"
requires-python = ">=3.10"
dependencies = []

[tool.hatch.build.targets.wheel]
packages = ["src/custom_echo_agent"]
src-path = "src"
```

Create an empty `__init__.py` file in the `src/custom_echo_agent/` directory so Python recognizes it as a package.

## Step 2: Write the Tool

Create `src/custom_echo_agent/tools.py` with your tool function:

```python
import logging
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext

log = logging.getLogger(__name__)

async def echo_tool(
    message: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Echoes the input message back."""
    current_config = tool_config if tool_config is not None else {}
    prefix = current_config.get("prefix", "Echo: ")

    result = f"{prefix}{message}"
    log.info(f"[EchoTool] Echoing: {result}")

    return {
        "status": "success",
        "message": result,
    }
```

Every tool function must be `async`. The `tool_context` and `tool_config` parameters are always the last two---SAM injects them automatically at runtime. All other parameters become the tool's input schema that the LLM sees and populates. In this example the LLM will see a single `message` string parameter. The `google.adk.tools` package is already included in the SAM Enterprise base image, so you do not need to install it separately.

## Step 3: Write the Agent YAML

Create `custom-echo-agent.yaml` to define the agent. This file is passed to Helm at deploy time via `--set-file config.yaml=custom-echo-agent.yaml`. All `${...}` variables are resolved at runtime from environment variables that the Helm chart injects---you do not need to hardcode any values:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: custom-echo-agent.log

shared_config:
  - broker_connection: &broker_connection
      dev_mode: ${SOLACE_DEV_MODE, false}
      broker_url: ${SOLACE_BROKER_URL, ws://localhost:8080}
      broker_username: ${SOLACE_BROKER_USERNAME, default}
      broker_password: ${SOLACE_BROKER_PASSWORD, default}
      broker_vpn: ${SOLACE_BROKER_VPN, default}
      temporary_queue: ${USE_TEMPORARY_QUEUES, true}

  - models:
    general: &general_model
      model: ${LLM_SERVICE_GENERAL_MODEL_NAME}
      api_base: ${LLM_SERVICE_ENDPOINT}
      api_key: ${LLM_SERVICE_API_KEY}

  - services:
    session_service: &default_session_service
      type: "memory"
      default_behavior: "PERSISTENT"

    artifact_service: &default_artifact_service
      type: "memory"

apps:
  - name: custom-echo-agent-app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      supports_streaming: true
      agent_name: "CustomEchoAgent"
      display_name: "Custom Echo Agent"
      model: *general_model

      instruction: |
        You are a custom echo agent. When a user sends you a message,
        use the echo_tool to echo it back to them.

      tools:
        - tool_type: python
          component_module: custom_echo_agent.tools
          function_name: echo_tool
          tool_config:
            prefix: "Echo: "

      session_service: *default_session_service
      artifact_service: *default_artifact_service

      agent_card:
        description: "A custom agent that echoes messages back"
        defaultInputModes: ["text"]
        defaultOutputModes: ["text"]
        skills:
          - id: "echo_tool"
            name: "Echo Tool"
            description: "Echoes the input message back to the user"

      agent_card_publishing: { interval_seconds: 10 }
      agent_discovery: { enabled: false }
      inter_agent_communication:
        allow_list: []
        request_timeout_seconds: 30
```

The `component_module` field points to the Python module path of your tool (`custom_echo_agent.tools`), and `function_name` identifies which function to load. The `tool_config` section provides configuration values that SAM passes to your function's `tool_config` parameter at runtime.

## Step 4: Build the Docker Image

Your project directory should look like this before building:

```
your-project/
├── Dockerfile
├── custom-echo-agent.yaml
└── custom-echo-agent/
    ├── pyproject.toml
    └── src/custom_echo_agent/
        ├── __init__.py
        └── tools.py
```

Create the following `Dockerfile`. It extends the SAM Enterprise base image, builds your plugin as a wheel, installs it, and fixes filesystem ownership so the runtime user can write to the SAM data directory:

```dockerfile
FROM <your-registry>/solace-agent-mesh-enterprise:<your-version>

USER 0
WORKDIR /app

# Install the build package (not included in the runtime image)
RUN pip install build

# Copy and build the custom plugin
COPY custom-echo-agent/ /tmp/custom-echo-agent/
RUN sam plugin build /tmp/custom-echo-agent && \
    pip install /tmp/custom-echo-agent/dist/*.whl && \
    rm -rf /tmp/custom-echo-agent

# Fix ownership: sam plugin build creates /app/.sam as root,
# but the runtime user (solaceai) needs write access
RUN chown -R solaceai:solaceai /app/.sam

USER solaceai

ENV SAM_CLI_HOME=/app/.sam
ENTRYPOINT ["solace-agent-mesh"]
CMD ["run", "/preset/agents"]
```

The image temporarily switches to `USER 0` (root) to install build tools and compile the plugin. The `sam plugin build` command produces a wheel under the plugin's `dist/` directory, which `pip install` then installs into the image's Python environment. After cleanup, `chown` ensures the SAM data directory is writable by the non-root `solaceai` user that runs at runtime.

:::info
The `pip install build` step requires internet access during image build. This is the same build pattern used in the SAM Enterprise Dockerfile itself. In air-gapped environments, pre-download the `build` package and COPY it into the image.
:::

## Step 5: Push to Registry

Build and push the image using Docker or Podman:

```bash
docker build -t <your-registry>/custom-echo-agent:1.0.0 .
docker push <your-registry>/custom-echo-agent:1.0.0
```

```bash
podman build . -t <your-registry>/custom-echo-agent:1.0.0
podman push <your-registry>/custom-echo-agent:1.0.0
```

Tag images with a version number rather than relying on `latest`. This makes rollbacks straightforward and ensures Kubernetes pulls the exact image you intend.

## Adapting for Your Own Agent

| What to change | Echo example | Your agent |
|----------------|-------------|------------|
| Plugin directory | `custom-echo-agent/` | `my-agent/` |
| Python package | `custom_echo_agent` | `my_agent` (underscores) |
| `component_module` in YAML | `custom_echo_agent.tools` | `my_agent.tools` |
| `agent_name` in YAML | `CustomEchoAgent` | `MyAgent` (PascalCase) |
| Helm release name | `custom-echo-agent` | `my-agent` (kebab-case) |

To expose multiple tools from a single agent, add additional entries under `tools` and match them in `agent_card.skills`:

```yaml
tools:
  - tool_type: python
    component_module: my_agent.tools
    function_name: first_tool

  - tool_type: python
    component_module: my_agent.tools
    function_name: second_tool
```

If your tool has third-party dependencies, add them to the `dependencies` list in `pyproject.toml`. In air-gapped environments the dependencies must already be present in the base image or copied into the build as local `.whl` files.

## Troubleshooting

:::warning
The `sam plugin build` command creates `/app/.sam` as root. If you forget the `RUN chown -R solaceai:solaceai /app/.sam` line in your Dockerfile, the container will fail at runtime with a `PermissionError` because the `solaceai` user cannot write to that directory.
:::

If you see `ModuleNotFoundError: No module named 'custom_echo_agent'` (or your package name) at runtime, the plugin was not installed correctly during the image build. Verify the install by running `docker run --rm <your-image> pip list | grep custom` against your built image. Check that the `packages` and `src-path` settings in `pyproject.toml` match your directory layout.

## Next Steps

- Deploy your image to Kubernetes using the [Agent and Workflow Deployment](https://solaceproducts.github.io/solace-agent-mesh-helm-quickstart/docs/standalone-agent-deployment) guide
- Learn more about tool development patterns in [Creating Python Tools](../creating-python-tools.md)
- Explore plugin packaging in detail at [Plugins](../../components/plugins.md)
