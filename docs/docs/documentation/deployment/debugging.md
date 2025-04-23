---
title: Debugging
sidebar_position: 30
---

# Debugging

Debugging issues in Solace Agent Mesh starts with identifying the problem. You can monitor your system to better debug your system. For more information, see [Observability](./observability.md).
The following sections provide common debugging approaches to help you to diagnose and resolve issues.

## Isolate Components

Running only the necessary components in isolation can help pinpoint issues. The `run` Solace Agent Mesh (SAM) CLI command allows you to specify which files to run.

For example:

```bash
sam run build/configs/agent_my_tool_1.yaml build/configs/agent_my_tool_2.yaml
```

This command runs only the agents defined in `agent_my_tool_1.yaml` and `agent_my_tool_2.yaml`, reducing noise from unrelated components.

## Examine STIM Files

[STIM files](./observability.md#stimulus-logs) provide detailed traces of stimulus life cycles. If you have access to the storage location where the [File Service](../user-guide/advanced/services/file-service.md) stores these files, you can inspect them to analyze message flows.

:::tip
If you don’t have direct access to the File service storage, you can use the File service’s download method to retrieve STIM files:

```python
from solace_agent_mesh.common.constants import SOLACE_AGENT_MESH_SYSTEM_SESSION_ID
```

Use `SOLACE_AGENT_MESH_SYSTEM_SESSION_ID` as the session ID to download relevant STIM files.
:::

Each `.stim` file contains all broker events related to a single stimulus, from the initial request to the final response.

## Monitor Broker Activity

For insights into message flows and event interactions, see [Broker Observability](./observability.md#broker-observability).

## Debug Mode

Since Solace Agent Mesh is a Python-based program and framework, you can run it in debug mode using an IDE with breakpoints.

### Debugging in VSCode

If you're using VSCode, configure debugging in `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "sam-debug",
      "type": "debugpy",
      "request": "launch",
      "module": "solace_agent_mesh.cli.main",
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env",
      "args": [
        "run",
        "-b",
        "build/configs/orchestrator.yaml",
        "build/configs/service_llm.yaml",
        "build/configs/service_embedding.yaml",
        "build/configs/agent_global.yaml"
        // Add any other components you want to run here
      ],
      "justMyCode": false
    }
  ]
}
```

To start debugging:
1. Open the **RUN AND DEBUG** panel on the left sidebar.
2. Select `sam-debug` from the dropdown.
3. Click the **Play** to start in debug mode.

Set breakpoints in your code to pause execution and inspect variable states.

## Invoke the Agent Directly

For debugging and testing, you can send direct messages to an agent using the PubSub+ event broker. This requires specifying the appropriate topic, user properties, and payload.

#### Tools for Sending Messages
- **[Solace Try Me VSCode Extension](https://marketplace.visualstudio.com/items?itemName=solace-tools.solace-try-me-vsc-extension)**
- **[Solace Try Me (STM) CLI Tool](https://github.com/SolaceLabs/solace-tryme-cli)**

#### Message Format

**Topic**:

```
[NAME_SPACES]solace-agent-mesh/v1/actionRequest/origin/agent/<agent_name>/<action_name>
```

**User Properties**:

```
session_id: test-0000
stimulus_uuid: 0000000-0000-0000-0000-000000000000
```

**Payload**:

```json
{
    "agent_name": "<agent_name>",
    "action_name": "<action_name>",
    "action_params": {
      "key": "action parameter"
    },
    "action_idx": 0,
    "action_list_id": "0000000-0000-0000-0000-000000000000"
}
```

**Response Topic**:

```
[NAME_SPACES]solace-agent-mesh/v1/actionResponse/agent/<agent_name>/<action_name>
```

By sending a request and observing the response, you can verify an agent's behavior in isolation, making it easier to identify issues.

## System Logs

System logs provide additional insights into the system's behavior. These logs are written to a log file at the root of the project directory.

:::info
The log level can be adjusted in the `solace-agent-mesh.yaml` configuration file. For more information, see [Configuration](../getting-started/configuration.md#build-settings).
:::

All input/output messages, warnings, and errors are logged to help your understanding of the the system's state and identify potential issues.
