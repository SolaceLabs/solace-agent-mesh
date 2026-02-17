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

To add a new component, such as an agent, gateway, or proxy, use the `add` command with the appropriate options.

```sh
sam add [agent|gateway|proxy] [OPTIONS] NAME
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

#### Add `proxy`

Use `proxy` to add an A2A proxy component that bridges external HTTP-based agents to the Solace Agent Mesh.

```sh
sam add proxy [OPTIONS] [NAME]
```

The proxy command creates a configuration file in `configs/agents/` that you can customize to connect external agents to the mesh.

##### Options:

- `--skip` – Skip interactive prompts and create the proxy with default template.
- `-h, --help` – Displays the help message and exits.

##### Example:

```sh
sam add proxy myProxy --skip
```

This creates `configs/agents/my_proxy_proxy.yaml` with the default proxy configuration template.



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



### `tools` - Manage and Explore Built-in Tools

The `tools` command allows you to explore and manage built-in tools available in Solace Agent Mesh.

```sh
sam tools [COMMAND] [OPTIONS]
```

#### `list` - List Built-in Tools

Lists all built-in tools available in Solace Agent Mesh. By default, shows brief information with tool names and descriptions.

```sh
sam tools list [OPTIONS]
```

This command is useful for:
- Discovering what built-in tools are available for your agents
- Understanding tool capabilities and required parameters
- Filtering tools by category
- Exporting tool information in JSON format

##### Options:

- `-c, --category TEXT` – Filter tools by category (e.g., 'artifact_management', 'data_analysis', 'web').
- `-d, --detailed` – Show detailed information including parameters and required scopes.
- `--json` – Output in JSON format instead of pretty table.
- `-h, --help` – Displays the help message.

For more information about built-in tools, see [Built-in Tools](builtin-tools/)

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

### `task` - Send Tasks to the Gateway

The `task` command allows you to send tasks to the webui gateway from the command line and receive streaming responses. This is useful for testing agents, debugging workflows, and automating interactions without using a browser.

```sh
sam task [COMMAND] [OPTIONS]
```

#### `run` - Start SAM, Send Task, and Stop

Starts SAM with specified configurations, waits for agents to be ready, sends a task, streams the response, and then cleanly shuts down. This is the recommended approach for one-shot testing and CI/CD pipelines.

```sh
sam task run [OPTIONS] MESSAGE
```

##### Basic Examples:

```sh
# Basic usage with default configs/ directory
sam task run "What agents are available?"

# Specify config files
sam task run "Hello" -c examples/agents/orchestrator.yaml -c examples/gateways/webui.yaml

# With file attachment
sam task run "Summarize this document" --file ./document.pdf -c configs/

# Target specific agent
sam task run "Analyze data" --agent data_analyst -c configs/

# Debug mode to see startup and SSE details
sam task run "Test" --debug -c configs/
```

##### Options:

- `-c, --config PATH` – YAML config files or directories to run. Can be specified multiple times. (default: `configs/` directory)
- `-s, --skip TEXT` – File name(s) to exclude from configs (e.g., `-s my_agent.yaml`).
- `-u, --url TEXT` – Base URL of the webui gateway. Can also be set via `SAM_WEBUI_URL` environment variable. (default: `http://localhost:8000`)
- `-a, --agent TEXT` – Target agent name. Can also be set via `SAM_AGENT` environment variable. (default: `orchestrator`)
- `--session-id TEXT` – Session ID for context continuity. If not provided, a new UUID is generated.
- `-t, --token TEXT` – Bearer token for authentication. Can also be set via `SAM_AUTH_TOKEN` environment variable.
- `-f, --file PATH` – File(s) to attach to the message. Can be specified multiple times.
- `--timeout INTEGER` – Timeout in seconds for task execution. (default: 300)
- `--startup-timeout INTEGER` – Timeout in seconds for agent readiness. (default: 60)
- `-o, --output-dir PATH` – Output directory for artifacts, logs, and response files. (default: `/tmp/sam-task-run-{taskId}`)
- `-q, --quiet` – Suppress streaming output. Only shows the final summary.
- `--no-stim` – Do not fetch the STIM file on completion.
- `--system-env` – Use system environment variables only; do not load .env file.
- `--debug` – Enable debug output showing startup progress and SSE events.
- `-h, --help` – Displays the help message and exits.

##### Output Directory Structure:

When a task completes, the output directory contains:

```
/tmp/sam-task-run-{taskId}/
├── sam.log               # SAM backend logs (useful for debugging startup issues)
├── sse_events.yaml       # All SSE events in YAML format (for debugging)
├── response.txt          # User-facing text output (same as terminal output)
├── {taskId}.stim         # STIM file from the backend (task invocation log)
└── artifacts/            # Downloaded artifacts created by agents
```

#### `send` - Send a Task to Running SAM

Sends a message to an agent via an already-running webui gateway and streams the response. Use this when SAM is already running (e.g., started with `sam run` or a VSCode launch configuration).

```sh
sam task send [OPTIONS] MESSAGE
```

The command blocks until the task completes and streams the response text to the terminal. All SSE events are recorded for debugging purposes.

##### Basic Examples:

```sh
# Send a simple message
sam task send "What is the weather today?"

# Send to a specific agent
sam task send "Analyze this data" --agent data_analyst

# Continue a previous conversation
sam task send "What did we discuss?" --session-id abc-123-def-456

# Attach a file to the message
sam task send "Summarize this document" --file ./document.pdf

# Attach multiple files
sam task send "Compare these files" --file ./file1.txt --file ./file2.txt

# Use a custom gateway URL with authentication
sam task send "Hello" --url https://mygateway.com --token $MY_TOKEN
```

##### Options:

- `-u, --url TEXT` – Base URL of the webui gateway. Can also be set via `SAM_WEBUI_URL` environment variable. (default: `http://localhost:8000`)
- `-a, --agent TEXT` – Target agent name. The command fetches available agents and attempts to match the specified name (case-insensitive). Can also be set via `SAM_AGENT` environment variable. (default: `orchestrator`)
- `-s, --session-id TEXT` – Session ID for context continuity. Use the same session ID to continue a previous conversation. If not provided, a new UUID is generated.
- `-t, --token TEXT` – Bearer token for authentication. Can also be set via `SAM_AUTH_TOKEN` environment variable.
- `-f, --file PATH` – File(s) to attach to the message. Can be specified multiple times to attach multiple files.
- `--timeout INTEGER` – Timeout in seconds for the SSE connection. (default: 120)
- `-o, --output-dir PATH` – Output directory for artifacts, logs, and response files. (default: `/tmp/sam-task-{taskId}`)
- `-q, --quiet` – Suppress streaming output. Only shows the final summary.
- `--no-stim` – Do not fetch the STIM file on completion.
- `--debug` – Enable debug output showing SSE events and connection details.
- `-h, --help` – Displays the help message and exits.

##### Output Directory Structure:

When a task completes, the output directory contains:

```
/tmp/sam-task-{taskId}/
├── sse_events.yaml       # All SSE events in YAML format (for debugging)
├── response.txt          # User-facing text output (same as terminal output)
├── {taskId}.stim         # STIM file from the backend (task invocation log)
└── artifacts/            # Downloaded artifacts created by agents
    ├── report.md
    └── data.csv
```

##### Session Continuity:

To continue a conversation from a previous session, use the `--session-id` option with the session ID printed at the end of a previous task:

```sh
# First interaction
sam task send "Remember my name is Alice"
# Output includes: Session ID: abc-123-def-456

# Continue the conversation
sam task send "What is my name?" --session-id abc-123-def-456
# Agent recalls: "Your name is Alice"
```

##### Agent Discovery:

The command automatically fetches available agents from the gateway at startup. When specifying an agent:

1. **Exact match** – If the agent name matches exactly, it's used directly
2. **Case-insensitive match** – If no exact match, tries case-insensitive matching
3. **Partial match** – If still no match, tries partial matching
4. **Fallback** – If the specified agent is not found, falls back to the first available agent

If the specified agent cannot be found, the command displays available agents and uses the default.

##### Environment Variables:

| Variable | Description |
|----------|-------------|
| `SAM_WEBUI_URL` | Default gateway URL (equivalent to `--url`) |
| `SAM_AGENT` | Default target agent (equivalent to `--agent`) |
| `SAM_AUTH_TOKEN` | Default authentication token (equivalent to `--token`) |

