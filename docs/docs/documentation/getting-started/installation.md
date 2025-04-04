---
title: Installation
sidebar_position: 20
---

# Prerequisites
Before you begin, you need the following installed on your computer:

- Python 3.11 or later
- PIP (if you have `pip3`, you can alias it to `pip` with the command `alias pip=pip3`).
  
# Installation

[Solace Agent Mesh Module](https://pypi.org/project/solace-agent-mesh) comes with two components:
1. **Solace Agent Mesh (SAM) CLI**: To create, build, run, and extend Solace Agent Mesh.
2. **Solace Agent Mesh framework**: A Python-based framework that you can build upon to customize and extend the capabilities of Solace Agent Mesh.

Installing the PyPi package will install both the SAM CLI and the framework (which is built on the Python SDK).

:::tip
We recommend that you install the package in a virtual environment to avoid conflicts with other Python packages.
:::

<details>
    <summary>Creating a Virtual Environment</summary>

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

**Install Solace Agent Mesh**

1. The following command installs the Solace Agent Mesh (SAM) CLI in your environment:

```sh
pip install solace-agent-mesh
```

<details>
    <summary>Windows-Specific Setup</summary>

    **PlantUML Support**

    The functionality from PlantUML is not available on Windows.  To use PlantUML on Windows, we recommend you install SAM on Windows Subsystem for Linux (WSL).

    **Plotly Support**

    Windows Users: To enable Plotly visualization capabilities, you must install a specific version of the Kaleido package before launching the application:
    ```sh
    pip install --upgrade "kaleido==0.1.*"
    ```
    This step is required only for Windows environments.
</details>

2. Run the following SAM CLI command (`solace-agent-mesh`) to verify your installation:

```sh
solace-agent-mesh --version
```

:::tip
For easier access to the SAM CLI, it also comes with the `sam` alias.

```sh
sam --version
```
:::

To get the list of available commands, run:

```sh
solace-agent-mesh --help
```
