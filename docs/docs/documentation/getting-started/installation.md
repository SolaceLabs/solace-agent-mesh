---
title: Installation
sidebar_position: 20
---

# Prerequisites

Before you begin, make sure you have the following:

- **Python 3.10.16+**
- **pip** (usually included with Python) or **uv** (install [uv](https://docs.astral.sh/uv/getting-started/installation/))
- **Operating System**: macOS, Linux, or Windows (via [WSL](https://learn.microsoft.com/en-us/windows/wsl/))
- **LLM API key** from any major provider or your own custom endpoint.

# Installation

[Solace Agent Mesh Module](https://pypi.org/project/solace-agent-mesh) comes with two components:
1. **Solace Agent Mesh CLI**: To create, build, run, and extend Solace Agent Mesh.
2. **Solace Agent Mesh framework**: A Python-based framework that you can build upon to customize and extend the capabilities of Solace Agent Mesh.

Installing the PyPi package installs both the Solace Agent Mesh CLI and the framework (which is built on the Python SDK).

:::tip
We recommend that you install the package in a virtual environment to avoid conflicts with other Python packages.
:::

<details>
    <summary>Creating a Virtual Environment</summary>


<details>
    <summary>Using PIP</summary>

1. Create a virtual environment.

```
python3 -m venv .venv
```

2. Activate the environment.

   To activate on Linux or Unix platforms:
    ```sh
    source .venv/bin/activate
    ```

    To activate on Windows:

    ```cmd
    .venv\Scripts\activate
    ```
</details>

<details>

    <summary>Using UV</summary>

1. Create a virtual environment.

```
uv venv .venv
```

2. Activate the environment.

   To activate on Linux or Unix platforms:
    ```sh
    source .venv/bin/activate
    ```

    To activate on Windows:

    ```cmd
    .venv\Scripts\activate
    ```
3. Expose the following environment variables:
4. 
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

**Install Solace Agent Mesh**

1. The following command installs Solace Agent Mesh CLI in your environment:

<details>
    <summary>Using PIP</summary>

```sh
pip install solace-agent-mesh
```
</details>

<details>
    <summary>Using UV</summary>

```sh
uv pip install solace-agent-mesh
```
</details>

:::info Docker Alternative
Alternatively, you can use our pre-built Docker image to run Solace Agent Mesh CLI commands without a local Python installation. This is useful for quick tasks or CI/CD environments. Note that the pre-built Docker image is configured with group `solaceai` and non-root user `solaceai`.

To verify the installation using Docker, you can run:
```sh
docker run --rm solace/solace-agent-mesh:latest --version
```
This command pulls the latest image (if not already present) and executes `solace-agent-mesh --version` inside the container. The `--rm` flag ensures the container is removed after execution.

If the OS architecture on your host is not `linux/amd64`, you would need to add `--platform linux/amd64` when running container.

For more complex operations like building a project, you'll need to mount your project directory into the container. See the [Quick Start guide](./quick-start.md) for an example.
:::

:::warning Browser Requirement
The `Mermaid` agent requires a browser with headless mode support to be installed (it uses headless mode to render diagrams). Use `playwright` to install the browser dependencies. If you are using the Docker image, this is already included.

To install the browser dependencies, run:

```sh
playwright install
```
:::

2. Run the following Solace Agent Mesh CLI command (`solace-agent-mesh`) to verify your installation:

```sh
solace-agent-mesh --version
```

:::tip
For easier access to the Solace Agent Mesh CLI, it also comes with the `sam` alias.

```sh
sam --version
```
:::

To get the list of available commands, run:

```sh
solace-agent-mesh --help
```
