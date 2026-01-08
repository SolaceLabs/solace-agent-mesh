---
title: Installing Agent Mesh
sidebar_position: 310
---

# Prerequisites

Before you begin, ensure you have the following:

- **Python 3.10.16+**
- **pip** (usually included with Python) or **uv** (install [uv](https://docs.astral.sh/uv/getting-started/installation/))
- **Operating System**: macOS, Linux, or Windows (via [WSL](https://learn.microsoft.com/en-us/windows/wsl/))
- **LLM API key** from any major provider or your own custom endpoint

# Installation

The [Solace Agent Mesh Module](https://pypi.org/project/solace-agent-mesh) includes two components:
1. **Agent Mesh CLI**: Create, build, run, and extend Agent Mesh
2. **Agent Mesh framework**: A Python-based framework for customizing and extending SAM's capabilities

Installing the PyPI package provides both the Agent Mesh CLI and the framework (which is built on the Python SDK).

First, create a project directory and navigate into it:

```sh
mkdir my-sam && cd my-sam
```

:::tip
We recommend installing the package in a virtual environment to avoid conflicts with other Python packages.
:::

<details>
    <summary>Creating a Virtual Environment</summary>

<details>
    <summary>Using pip</summary>

1. Create a virtual environment:

```
python3 -m venv .venv
```

2. Activate the environment:

   On Linux or Unix platforms:
    ```sh
    source .venv/bin/activate
    ```

    On Windows:

    ```cmd
    .venv\Scripts\activate
    ```
</details>

<details>
    <summary>Using uv</summary>

1. Create a virtual environment:

```
uv venv .venv
```

2. Activate the environment:

   On Linux or Unix platforms:
    ```sh
    source .venv/bin/activate
    ```

    On Windows:

    ```cmd
    .venv\Scripts\activate
    ```

3. Set the following environment variables:

   On Linux or Unix platforms:
    ```sh
    export SAM_PLUGIN_INSTALL_COMMAND="uv pip install {package}"
    ```

    On Windows:
    ```cmd
    set SAM_PLUGIN_INSTALL_COMMAND="uv pip install {package}"
    ```
</details>

</details>

## Install Agent Mesh

The following command installs Agent Mesh CLI in your environment:

<details>
    <summary>Using pip</summary>

```sh
pip install solace-agent-mesh
```
</details>

<details>
    <summary>Using uv</summary>

```sh
uv pip install solace-agent-mesh
```
</details>

:::info Docker Alternative
Alternatively, you can use our pre-built Docker image to run Agent Mesh CLI commands without a local Python installation. This approach is useful for quick tasks or CI/CD environments. The pre-built Docker image is configured with group `solaceai` and non-root user `solaceai`.

To verify the installation using Docker, run:
```sh
docker run --rm solace/solace-agent-mesh:latest --version
```
This command pulls the latest image (if not already present) and executes `solace-agent-mesh --version` inside the container. The `--rm` flag ensures the container is removed after execution.

If your host OS architecture is not `linux/amd64`, you need to add `--platform linux/amd64` when running the container.

For more complex operations like building a project, you need to mount your project directory into the container. See the [Quick Start guide](../getting-started/try-agent-mesh.md) for examples.
:::

:::warning Browser Requirement
The `Mermaid` agent requires a browser with headless mode support to render diagrams. Use `playwright` to install the browser dependencies. If you are using the Docker image, this is already included.

To install the browser dependencies, run:

```sh
playwright install
```
:::

## Verify Installation

Run the following Agent Mesh CLI command to verify your installation:

```sh
solace-agent-mesh --version
```

:::tip
For easier access to the Agent Mesh CLI, you can also use the `sam` alias:

```sh
sam --version
```
:::

To get a list of available commands, run:

```sh
solace-agent-mesh --help
```

## Next Steps

After successful installation, choose your next step based on your goals:

**For Quick Exploration**: If you want to try SAM's capabilities immediately without project setup, use the [Docker quick start](../getting-started/try-agent-mesh.md) to explore SAM with minimal configuration.

**For Development Work**: If you're ready to build a complete project with full control over configuration, proceed directly to the [project setup guide](run-project.md).

**To Learn More**: Explore the system components by reading about [agents](../components/agents.md) and [gateways](../components/gateways.md).