---
title: Solace Agent Mesh CLI
sidebar_position: 5
toc_max_heading_level: 4
---

# Solace Agent Mesh CLI

Solace Agent Mesh comes with a comprehensive CLI tool that you can use to create, build, and run an instance of Solace Agent Mesh, which is referred to as a Solace Agent Mesh (SAM) application. The Solace Agent Mesh (SAM) CLI also allows you to add agents and gateways, update configurations, manage plugins, help you debug, and much more.

## Installation

The SAM CLI is installed as part of the package for Solace Agent Mesh. For more information, see [Installation](../getting-started/installation.md).

:::tip[CLI Tips]

- The Solace Agent Mesh CLI comes with a short alias of `sam` which can be used in place of `solace-agent-mesh`.
- You can determine the version of the SAM CLI by running `solace-agent-mesh --version`.
- You can get help on any command by running `solace-agent-mesh [COMMAND] --help`.
  :::

## Usage

### Global Options

These options apply globally to all commands and provide basic information or customization options:

```sh
sam --version               # Displays the installed version of the CLI and exits.
sam -c, --config-file PATH  # Specifies a custom configuration file to use.
sam -h, --help              # Displays the help message and exits.
```

## Commands

### `init` - Initialize a SAM Application

```sh
sam init [OPTIONS]
```

When this command is run with no options, it runs in interactive mode and prompts you to provide the necessary information to set up a SAM application.

You can skip some questions by providing the appropriate options for that step.

Optionally, you can skip all the questions by providing the `--skip` option. This option uses the provided or default values for all the questions.

:::tip[automated workflows]
Use the `--skip` option and provide the necessary options to run the command in non-interactive mode, useful for automated workflows.
:::

##### Options:

- `--skip` – Runs in non-interactive mode, using default values where available.
- `--namespace TEXT` – Defines a custom project namespace for better organization.
- `--config-dir TEXT` – Specifies the base directory where configuration files are stored.
- `--module-dir TEXT` – Sets the base directory for storing Python modules used in the system.
- `--build-dir TEXT` – Defines the directory where build outputs are stored.
- `--env-file TEXT` – Specifies the path to an environment file containing variable definitions.
- `--broker-type TEXT` – Defines the broker type (options: container, solace, dev_broker).
- `--broker-url TEXT` – Specifies the URL of the Solace broker for connectivity.
- `--broker-vpn TEXT` – Defines the virtual private network (VPN) name used by the broker.
- `--broker-username TEXT` – Sets the username for authenticating with the Solace broker.
- `--broker-password TEXT` – Specifies the password required for broker authentication.
- `--container-engine TEXT` – Defines which container engine to use (options: podman, docker).
- `--llm-model-name TEXT` – Specifies the LLM model name to be used in AI-related functions.
- `--llm-endpoint-url TEXT` – Sets the URL endpoint for the LLM model API.
- `--llm-api-key TEXT` – Provides the necessary API key for accessing the LLM endpoint.
- `--embedding-model-name TEXT` – Specifies the name of the embedding model to be used.
- `--embedding-endpoint-url TEXT` – Defines the URL endpoint for embedding model queries.
- `--embedding-api-key TEXT` – Provides the API key required for embedding model access.
- `--built-in-agent TEXT` – [MULTI] Lists built-in agents to use, such as `global` or `image_processing`.
- `--file-service-provider TEXT` – Specifies the file service provider (options: volume, bucket).
- `--file-service-config TEXT` – Supplies key-value pairs for configuring file services.
- `--env-var TEXT` – [MULTI] Defines key-value pairs to be included in the environment file.
- `--rest-api-enabled` – Flag to enable the REST API interface.
- `--rest-api-server-input-port TEXT` – Specifies the port number for the REST API server.
- `--rest-api-server-host TEXT` – Sets the host address for the REST API server.
- `--rest-api-server-input-endpoint TEXT` – Defines the endpoint path for REST API requests.
- `--rest-api-gateway-name TEXT` – Sets the name for the REST API gateway.
- `--webui-enabled` – Flag to enable the Web UI interface.
- `--webui-listen-port TEXT` – Specifies the port number for the Web UI server.
- `--webui-host TEXT` – Sets the host address for the Web UI server.
- `-h, --help` – Displays the help message and exits.

### `add` - Create a New Component

To add a new component, such as an agent or gateway, use the `add` command with the appropriate options.

```sh
sam add [agent|gateway] [OPTIONS] NAME
```

#### Add `agent`

Use `agent` to add an agent component.

- `-c, --copy-from TEXT` – Copies the configuration from an existing plugin for easier setup. (e.g., `--copy-from my-plugin:my-agent`)
- `-h, --help` – Displays the help message and exits.

For more information, see [Agents](../concepts/agents.md).

#### Add `gateway`

Use `gateway` to add a gateway component.

- `-i, --interface TEXT` – Adds interfaces (e.g., `--interface rest-api`) to expand functionality.
- `-c, --copy-from TEXT` – Copies configuration from an existing plugin for quick deployment. (e.g., `--copy-from my-plugin:my-gateway`)
- `-h, --help` – Displays the help message and exits.

For more information, see [Gateways](../concepts/gateways.md).

### `build` - Build a SAM Application

To build an instance of Solace Agent Mesh (a SAM application), use the `build` command.

```sh
sam build [OPTIONS]
```

:::note
The `build` command runs the `init` command if the file `solace-agent-mesh.yaml` is not found in the project root directory. You can skip running the `init` by providing the `-N` or `--no-init` option.
:::

##### Options:

- `-y` – Skips confirmation prompts for automated workflows. (Adds `--skip` for `init` command as well)
- `-N, --no-init` – Prevents running `init` automatically if not already executed.
- `-h, --help` – Displays the help message and exits.

### `run` - Run the SAM Application

To run the SAM application, use the `run` command.

```sh
sam run [OPTIONS] [FILES]...
```

:::tip[Load environment variables]
Use the `-e` or `--use-env` option to load environment variables from the configuration file.
:::

:::tip[none to run]
The `run` command includes built-in dependency handling. If the build directory is missing, it automatically executes the `build` command. Similarly, if the configuration file is not found, it automatically executes the `init` command.

To quickly get started, you can simply use the `run` command without manually executing `build` or `init`. To use default values during the `build` and `init` phases, add the `-q` or `--quick-build` option.
:::

While running the `run` command, you can also skip specific files by providing the `-s` or `--skip` option.

Or, you can only run the provided files by providing them as arguments. You might want to separate your project into multiple processes to meet your scaling needs. For more information, see [Deployment](../deployment/deploy.md).

For example:

```sh
solace-agent-mesh run -e build/configs/config1.yaml build/configs/config2.yaml
```

##### Options:

- `-e, --use-env` – Loads environment variables from the configuration for execution.
- `-s, --skip TEXT` – Skips specified files during execution.
- `-q, --quick-build` – Uses default behavior for `init` and `build` steps.
- `-i, --ignore-build` – Skips `build` if the build directory is missing.
- `-b, --force-build` – Forces `build` execution before running the SAM application.
- `-h, --help` – Displays the help message and exits.

### `chat` - Chat with a SAM Application

The `chat` command allows starting a chat with the SAM application using command line interface.

```sh
sam chat [COMMAND] [OPTIONS]
```

#### `login` - Authenticate to a SAM

Authenticate to the Solace Agent Mesh application.

```sh
sam chat login SERVER
```

The `SERVER` is the authentication server.

#### `logout` - Log out from a SAM

Log out from the Solace Agent Mesh application and remove tokens.

```sh
sam chat logout
```

#### `start` - Establish a chat with a SAM

Start a chat session with the Solace Agent Mesh application.

```sh
sam chat start [OPTIONS]
```

##### Options:

- `-s, --stream` – Enables streaming mode. (default is non-streaming mode)
- `-f, --file TEXT` – The path of attached file.
- `-a, --auth` – Enables authentication.
- `-u, --url` TEXT` – The chat service provider url.
- `-h, --help` – Displays the help message and exits.

### `plugin` - Manage Plugins

The `plugin` command allows you to manage plugins for SAM application.

```sh
sam plugin [COMMAND] [OPTIONS]
```

For more information, see [Plugins](../concepts/plugins/index.md).

#### `create` - Create a Plugin

Initializes and creates a new plugin with customizable options.

```sh
sam plugin create [OPTIONS] NAME
```

When this command is run with no options, it runs in interactive mode and prompts you to provide the necessary information to set up the plugin for Solace Agent Mesh

You can skip some questions by providing the appropriate options for that step.

Optionally, you can skip all the questions by providing the `--skip` option. This option uses the provided or default values for all the questions, which is useful for automated workflows.

##### Options:

- `-s, --skip` – Runs in non-interactive mode, using default values where applicable.
- `-n, --name TEXT` – Plugin name. (A path if it shouldn't be created in the current directory)
- `-d, --description TEXT` – Plugin description.
- `-a, --author TEXT` – Plugin author.
- `-h, --help` – Displays the help message and exits.

#### `build` - Build the Plugin

Compiles and prepares the plugin for use.

```sh
sam plugin build [OPTIONS]
```

##### Options:

- `-h, --help` – Displays the help message and exits.

#### `add` - Add an Existing Plugin

Adds an existing plugin to the configuration for Solace Agent Mesh.

```sh
sam plugin add [OPTIONS] NAME
```

##### Options:

- `--add-all` – Adds the plugin with the default of loading all exported files from the plugin.
- `--pip` – Install with pip.
- `--uv` - Install with uv pip.
- `--poetry` – Install with poetry.
- `--conda` – Install with conda.
- `-u, --from-url TEXT` – Install the plugin from a given URL instead of the given name. The URL can be a file path or a Git URL.
- `-h, --help` – Displays the help message and exits.

#### `remove` - Remove an Installed Plugin

Removes an installed plugin from the system.

```sh
sam plugin remove [OPTIONS] NAME
```

##### Options:

- `--pip-uninstall` – Removes the plugin module using pip.
- `--uv-uninstall` – Removes the plugin module using uv pip.
- `--poetry-uninstall` – Removes the plugin module using poetry.
- `--conda-uninstall` – Removes the plugin module using conda.
- `-h, --help` – Displays the help message and exits.

### `visualize` - Run a Web GUI Visualizer

Runs a web GUI visualizer for inspecting stimuli inside Solace Agent Mesh.

```sh
sam visualize [OPTIONS]
```

##### Options:

- `-p, --port INTEGER` – Specifies the port number for the web GUI.
- `-f, --find-unused-port` – Automatically selects the next available port if the specified one is in use.
- `-h, --host` – Exposes the visualizer to the network.
- `-e, --use-env` – Loads environment variables from the configuration file.
- `--help` – Displays the help message and exits.

For more information, see [Observability](../deployment/observability.md).

### `config` - Update the Configuration File

Updates the `solace-agent-mesh.yaml` configuration file with the latest default settings.

```sh
sam config [OPTIONS]
```

You only need to run the command when a new version of Solace Agent Mesh is released, and you want to update your configuration file to include the latest settings and options.

##### Options:

- `-h, --help` – Displays the help message and exits.

For more information, see [Configuration](../getting-started/configuration.md).
