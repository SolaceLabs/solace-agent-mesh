---
title: Agent Mesh CLI
sidebar_position: 280
toc_max_heading_level: 4
---

# Agent Mesh CLI

Agent Mesh comes with a comprehensive CLI tool that you can use to create, and run an instance of Agent Mesh, which is referred to as an Agent Mesh application. Agent Mesh CLI also allows you to add agents and gateways, manage plugins, help you debug, and much more.

## Installation

The Agent Mesh CLI is installed as part of the Agent Mesh package. For more information, see [Installation](../installing-and-configuring/installation.md).

:::tip[CLI Tips]

- The Agent Mesh CLI comes with a short alias of `sam` which can be used in place of `solace-agent-mesh`.
- You can determine the version of the Agent Mesh CLI by running `solace-agent-mesh --version`.
- You can get help on any command by running `solace-agent-mesh [COMMAND] --help`.
  :::


## Commands

### `init` - Initialize an Agent Mesh Application

```sh
sam init [OPTIONS]
```

When this command is run with no options, it runs in interactive mode. It first prompts you to choose between configuring your project in the terminal or through a browser-based interface.

If you choose to use the browser, the Agent Mesh CLI starts a local web configuration portal, available at `http://127.0.0.1:5002`

You can skip some questions by providing the appropriate options for that step during the Agent Mesh CLI-based setup.

Optionally, you can skip all the questions by providing the `--skip` option. This option uses the provided or default values for all the questions.

:::tip[automated workflows]
Use the `--skip` option and provide the necessary options to run the command in non-interactive mode, useful for automated workflows.
:::

##### Options:

- `--gui` – Launch the browser-based initialization interface directly, skipping the prompt. (Recommended way to configure Agent Mesh applications)
- `--skip` – Runs in non-interactive mode, using default values where available.
- `--llm-service-endpoint TEXT` – LLM Service Endpoint URL.
- `--llm-service-api-key TEXT` – LLM Service API Key.
- `--llm-service-planning-model-name TEXT` – LLM Planning Model Name.
- `--llm-service-general-model-name TEXT` – LLM General Model Name.
- `--namespace TEXT` – Namespace for the project.
- `--broker-type TEXT` – Broker type: 1/solace (existing), 2/container (new local), 3/dev (dev mode). Options: 1, 2, 3, solace, container, dev_mode, dev_broker, dev.
- `--broker-url TEXT` – Solace broker URL endpoint.
- `--broker-vpn TEXT` – Solace broker VPN name.
- `--broker-username TEXT` – Solace broker username.
- `--broker-password TEXT` – Solace broker password.
- `--container-engine TEXT` – Container engine for local broker. Options: podman, docker.
- `--dev-mode` – Shortcut to select dev mode for broker (equivalent to --broker-type 3/dev).
- `--agent-name TEXT` – Agent name for the main orchestrator.
- `--supports-streaming` – Enable streaming support for the agent.
- `--session-service-type TEXT` – Session service type. Options: memory, vertex_rag.
- `--session-service-behavior TEXT` – Session service behavior. Options: PERSISTENT, RUN_BASED.
- `--artifact-service-type TEXT` – Artifact service type. Options: memory, filesystem, gcs.
- `--artifact-service-base-path TEXT` – Artifact service base path (for filesystem type).
- `--artifact-service-scope TEXT` – Artifact service scope. Options: namespace, app, custom.
- `--artifact-handling-mode TEXT` – Artifact handling mode. Options: ignore, embed, reference.
- `--enable-embed-resolution` – Enable embed resolution.
- `--enable-artifact-content-instruction` – Enable artifact content instruction.
- `--enable-builtin-artifact-tools` – Enable built-in artifact tools.
- `--enable-builtin-data-tools` – Enable built-in data tools.
- `--agent-card-description TEXT` – Agent card description.
- `--agent-card-default-input-modes TEXT` – Agent card default input modes (comma-separated).
- `--agent-card-default-output-modes TEXT` – Agent card default output modes (comma-separated).
- `--agent-discovery-enabled` – Enable agent discovery.
- `--agent-card-publishing-interval INTEGER` – Agent card publishing interval (seconds).
- `--inter-agent-communication-allow-list TEXT` – Inter-agent communication allow list (comma-separated, use * for all).
- `--inter-agent-communication-deny-list TEXT` – Inter-agent communication deny list (comma-separated).
- `--inter-agent-communication-timeout INTEGER` – Inter-agent communication timeout (seconds).
- `--add-webui-gateway` – Add a default Web UI gateway configuration.
- `--webui-session-secret-key TEXT` – Session secret key for Web UI.
- `--webui-fastapi-host TEXT` – Host for Web UI FastAPI server.
- `--webui-fastapi-port INTEGER` – Port for Web UI FastAPI server.
- `--webui-enable-embed-resolution` – Enable embed resolution for Web UI.
- `--webui-frontend-welcome-message TEXT` – Frontend welcome message for Web UI.
- `--webui-frontend-bot-name TEXT` – Frontend bot name for Web UI.
- `--webui-frontend-logo-url TEXT` – URL to a custom logo image for the Web UI interface. Supports PNG, SVG, JPG formats, as well as data URIs for embedded images.
- `--webui-frontend-collect-feedback` – Enable feedback collection in Web UI.
- `-h, --help` – Displays the help message and exits.

### `add` - Create a New Component

To add a new component, such as an agent or gateway, use the `add` command with the appropriate options.

```sh
sam add [agent|gateway] [OPTIONS] NAME
```

#### Add `agent`

Use `agent` to add an agent component.

```sh
sam add agent [OPTIONS] [NAME]
```

##### Options:

- `--gui` – Launch the browser-based configuration interface for agent setup. (Recommended way to configure agents)
- `--skip` – Skip interactive prompts and use defaults (Agent Mesh CLI mode only).
- `--namespace TEXT` – namespace (for example, myorg/dev).
- `--supports-streaming BOOLEAN` – Enable streaming support.
- `--model-type TEXT` – Model type for the agent. Options: planning, general, image_gen, report_gen, multimodal, gemini_pro.
- `--instruction TEXT` – Custom instruction for the agent.
- `--session-service-type TEXT` – Session service type. Options: memory, vertex_rag.
- `--session-service-behavior TEXT` – Session service behavior. Options: PERSISTENT, RUN_BASED.
- `--artifact-service-type TEXT` – Artifact service type. Options: memory, filesystem, gcs.
- `--artifact-service-base-path TEXT` – Base path for filesystem artifact service.
- `--artifact-service-scope TEXT` – Artifact service scope. Options: namespace, app, custom.
- `--artifact-handling-mode TEXT` – Artifact handling mode. Options: ignore, embed, reference.
- `--enable-embed-resolution BOOLEAN` – Enable embed resolution.
- `--enable-artifact-content-instruction BOOLEAN` – Enable artifact content instruction.
- `--enable-builtin-artifact-tools BOOLEAN` – Enable built-in artifact tools.
- `--enable-builtin-data-tools BOOLEAN` – Enable built-in data tools.
- `--agent-card-description TEXT` – Description for the agent card.
- `--agent-card-default-input-modes-str TEXT` – Comma-separated default input modes for agent card.
- `--agent-card-default-output-modes-str TEXT` – Comma-separated default output modes for agent card.
- `--agent-card-publishing-interval INTEGER` – Agent card publishing interval in seconds.
- `--agent-discovery-enabled BOOLEAN` – Enable agent discovery.
- `--inter-agent-communication-allow-list-str TEXT` – Comma-separated allow list for inter-agent communication.
- `--inter-agent-communication-deny-list-str TEXT` – Comma-separated deny list for inter-agent communication.
- `--inter-agent-communication-timeout INTEGER` – Timeout in seconds for inter-agent communication.
- `-h, --help` – Displays the help message and exits.

For more information, see [Agents](agents.md).

#### Add `gateway`

Use `gateway` to add a gateway component.

```sh
sam add gateway [OPTIONS] [NAME]
```

##### Options:

- `--gui` – Launch the browser-based configuration interface for gateway setup. (Recommended way to configure gateways)
- `--skip` – Skip interactive prompts and use defaults (Agent Mesh CLI mode only).
- `--namespace TEXT` – namespace for the gateway (for example, myorg/dev).
- `--gateway-id TEXT` – Custom Gateway ID for the gateway.
- `--artifact-service-type TEXT` – Artifact service type for the gateway. Options: memory, filesystem, gcs.
- `--artifact-service-base-path TEXT` – Base path for filesystem artifact service (if type is 'filesystem').
- `--artifact-service-scope TEXT` – Artifact service scope (if not using default shared artifact service). Options: namespace, app, custom.
- `--system-purpose TEXT` – System purpose for the gateway (can be multi-line).
- `--response-format TEXT` – Response format for the gateway (can be multi-line).
- `-h, --help` – Displays the help message and exits.

For more information, see [Gateways](gateways.md).



### `run` - Run the Agent Mesh Application

To run the Agent Mesh application, use the `run` command.

```sh
sam run [OPTIONS] [FILES]...
```

:::info[Environment variables]
The `sam run` command automatically loads environment variables from your configuration file (typically a `.env` file at the project root) by default.

If you want to use your system's environment variables instead, you can add the `-u` or `--system-env` option.
:::

While running the `run` command, you can also skip specific files by providing the `-s` or `--skip` option.

You can provide paths to specific YAML configuration files or directories. When you provide a directory, `run` will recursively search for and load all `.yaml` and `.yml` files within that directory. This allows you to organize your configurations and run them together easily.

For example, to run specific files:

```sh
solace-agent-mesh run configs/agent1.yaml configs/gateway.yaml
```

To run all YAML files within the `configs` directory:

```sh
solace-agent-mesh run configs/
```

##### Options:

- `-u, --system-env` – Use system environment variables only; do not load .env file.
- `-s, --skip TEXT` – File name(s) to exclude from the run (for example, -s my_agent.yaml).
- `-h, --help` – Displays the help message and exits.

### `docs` - Serve the documentation locally

Serves the project documentation on a local web server.

```sh
sam docs [OPTIONS]
```

This command starts a web server to host the documentation, which is useful for offline viewing or development. By default, it serves the documentation at `http://localhost:8585/solace-agent-mesh/` and automatically opens your web browser to the getting started page.

If a requested page is not found, it will redirect to the main documentation page.

##### Options:

-   `-p, --port INTEGER` – Port to run the web server on. (default: 8585)
-   `-h, --help` – Displays the help message and exits.



### `plugin` - Manage Plugins

The `plugin` command allows you to manage plugins for Agent Mesh application.

```sh
sam plugin [COMMAND] [OPTIONS]
```

For more information, see [Plugins](plugins.md).

#### `create` - Create a Plugin

Initializes and creates a new plugin with customizable options.

```sh
sam plugin create [OPTIONS] NAME
```

When this command is run with no options, it runs in interactive mode and prompts you to provide the necessary information to set up the plugin for Agent Mesh.

You can skip some questions by providing the appropriate options for that step.

Optionally, you can skip all the questions by providing the `--skip` option. This option uses the provided or default values for all the questions, which is useful for automated workflows.

##### Options:

- `--type TEXT` – Plugin type. Options: agent, gateway, custom.
- `--author-name TEXT` – Author's name.
- `--author-email TEXT` – Author's email.
- `--description TEXT` – Plugin description.
- `--version TEXT` – Initial plugin version.
- `--skip` – Skip interactive prompts and use defaults or provided flags.
- `-h, --help` – Displays the help message and exits.

#### `build` - Build the Plugin

Compiles and prepares the plugin for use.

```sh
sam plugin build [PLUGIN_PATH]
```

Builds the Agent Mesh plugin in the specified directory (defaults to current directory).

##### Options:

- `PLUGIN_PATH` – Path to the plugin directory (defaults to current directory).
- `-h, --help` – Displays the help message and exits.

#### `add` - Add an Existing Plugin

Installs the plugins and creates a new component instance from a specified plugin source.

```sh
sam plugin add [OPTIONS] COMPONENT_NAME
```

##### Options:

- `--plugin TEXT` – Plugin source: installed module name, local path, or Git URL. (Required)
- `--install-command TEXT` – Command to use to install a python package. Must follow the format `command {package} args`, by default `pip3 install {package}`. Can also be set through the environment variable SAM_PLUGIN_INSTALL_COMMAND.
- `-h, --help` – Displays the help message and exits.


#### `installs` - Installs a Plugin

Installs a plugin from a specified plugin source.

```sh
sam plugin install [OPTIONS] PLUGIN_SOURCE
```

PLUGIN_SOURCE can be:
  - A local path to a directory (e.g., '/path/to/plugin')
  - A local path to a wheel file (e.g., '/path/to/plugin.whl')
  - A Git URL (e.g., 'https://github.com/user/repo.git')
  - The name of the plugin from https://github.com/SolaceLabs/solace-agent-mesh-core-plugins

##### Options:

- `--install-command TEXT` – Command to use to install a python package. Must follow the format `command {package} args`, by default `pip3 install {package}`. Can also be set through the environment variable SAM_PLUGIN_INSTALL_COMMAND.
- `-h, --help` – Displays the help message and exits.

#### `catalog` - Launch Plugin Catalog

Launch the Agent Mesh Plugin Catalog web interface.

```sh
sam plugin catalog [OPTIONS]
```

##### Options:

- `--port INTEGER` – Port to run the plugin catalog web server on. (default: 5003)
- `--install-command TEXT` – Command to use to install a python package. Must follow the format `command {package} args`.
- `-h, --help` – Displays the help message and exits.

