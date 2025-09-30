---
title: Debugging
sidebar_position: 30
---

# Debugging

Debugging issues in Solace Agent Mesh starts with identifying the problem. You can monitor your system to debug it more effectively. For more information, see [Observability](./observability.md).
The following sections provide common debugging approaches to help you diagnose and resolve issues.

## Isolate Components

Running only the necessary components in isolation can help pinpoint issues. The `run` Solace Agent Mesh CLI command allows you to specify which files to run.

For example:

```bash
sam run configs/agents/my_tool_1.yaml configs/agents/my_tool_2.yaml
```

This command runs only the agents defined in `my_tool_1.yaml` and `my_tool_2.yaml`, reducing noise from unrelated components.

## Examine STIM Files

[STIM files](./observability.md#stimulus-logs) provide detailed traces of stimulus life cycles. If you have access to the storage location, you can inspect them to analyze message flows.

Each `.stim` file contains all broker events related to a single stimulus, from the initial request to the final response.

## Monitor Broker Activity

For insights into message flows and event interactions, see [Broker Observability](./observability.md#broker-observability).

## Debug Mode

Because Solace Agent Mesh is a Python-based framework, you can run it in debug mode using an IDE with breakpoints.

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
        "configs/agents/main_orchestrator.yaml",
        "configs/gateways/webui.yaml"
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

For debugging and testing, you can send direct messages to an agent by directly selecting the agent in the web UI agent dropdown or by using the Solace event broker. This requires specifying the appropriate topic, user properties, and payload.

#### Tools for Sending Messages
- **[Solace Try Me VSCode Extension](https://marketplace.visualstudio.com/items?itemName=solace-tools.solace-try-me-vsc-extension)**
- **[Solace Try Me (STM) CLI Tool](https://github.com/SolaceLabs/solace-tryme-cli)**

#### Message Format

**Topic**:

```
[NAME_SPACES]a2a/v1/agent/request/<agent_name>
```

**User Properties**:

```
userId: test-0000
clientId: test-0000
replyTo: [NAME_SPACES]a2a/v1/gateway/response/0000000/task-0000000
a2aUserConfig: {}
```

**Payload**:

```json
{
    "jsonrpc": "2.0",
    "id": "000000000",
    "method": "tasks/sendSubscribe",
    "params": {
      "id": "task-0000000",
      "sessionId": "web-session-00000000",
      "message": {
        "role": "user",
        "parts": [
          {
            "type": "text",
            "text": "Hello World!"
          }
        ]
      },
      "acceptedOutputModes": [
        "text"
      ],
      "metadata": {
        "system_purpose": "The system is an AI Chatbot with agentic capabilities. It uses the agents available to provide information, reasoning and general assistance for the users in this system. **Always return useful artifacts and files that you create to the user.** Provide a status update before each tool call. Your external name is Agent Mesh.\n",
        "response_format": "Responses should be clear, concise, and professionally toned. Format responses to the user in Markdown using appropriate formatting.\n"
      }
  }
}
```

**Response Topic**:

```
[NAME_SPACES]a2a/v1/gateway/response/0000000/task-0000000
```

By sending a request and observing the response, you can verify an agent's behavior in isolation, making it easier to identify issues.

## System Logs

System logs provide detailed insights into the system's behavior. The logging behavior is configured in the `configs/logging_config.ini` file, which controls both console (STDOUT) and file-based logging.

By default, the system is configured to:
- Output logs with a severity of `INFO` and higher to the console (STDOUT).
- Write more detailed logs with a severity of `DEBUG` and higher to a rotating log file named `sam.log` in the project's root directory.

### Configuring Log Rotation

The log file rotation is managed by the `rotatingFileHandler` in `configs/logging_config.ini`. You can customize its behavior by modifying the `args` line:

```ini
[handler_rotatingFileHandler]
class=logging.handlers.RotatingFileHandler
level=DEBUG
formatter=simpleFormatter
args=('sam.log', 'a', 52428800, 10)
```

The `args` tuple is defined as follows:
- `'sam.log'`: The name of the log file.
- `'a'`: The file mode (append).
- `52428800`: The maximum size of the log file in bytes before it is rotated. In this case, it's 50 MB.
- `10`: The number of backup log files to keep.

For example, to change the log file size to 20 MB and keep 5 backup files, you would modify the line to:
`args=('sam.log', 'a', 20971520, 5)`

This level of configuration allows you to manage log verbosity and disk space usage according to your needs.
