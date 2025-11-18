---
title: Diagnosing and Resolving Problems
sidebar_position: 30
---

# Diagnosing and Resolving Problems

Effective debugging in Agent Mesh requires a systematic approach that leverages the platform's distributed architecture. Because your system consists of multiple agents communicating through a Solace event broker, issues can arise at various levels—from individual agent logic to inter-component communication patterns.

The key to successful debugging lies in understanding where problems might occur and having the right tools to investigate each layer of your system. Agent Mesh provides comprehensive observability features that serve as your foundation for debugging activities. For detailed information about these monitoring capabilities, see [Observability](./observability.md).

This guide presents proven debugging strategies arranged from simple isolation techniques to advanced diagnostic methods. Each approach targets different types of issues, allowing you to choose the most effective method based on your specific situation.

## Isolating Components

When facing complex issues in a multi-agent system, isolation becomes your most powerful debugging technique. By running only the components directly related to your problem, you eliminate variables and focus your investigation on the most likely sources of trouble.

Component isolation works because it reduces system complexity to manageable levels. Instead of trying to understand interactions across dozens of agents, you can focus on a small subset and verify their behavior in controlled conditions.

The Agent Mesh CLI provides precise control over which components run in your debugging session. You can specify exactly which configuration files to load, creating a minimal environment that includes only the agents you need to investigate.

For example, if you're debugging an issue with a specific tool integration, you might run only the orchestrator and the problematic tool agent:

```bash
sam run configs/agents/my_tool_1.yaml configs/agents/my_tool_2.yaml
```

This command creates a focused debugging environment that includes only the agents defined in `my_tool_1.yaml` and `my_tool_2.yaml`. By eliminating unrelated components, you reduce log noise and make it easier to trace the specific interactions that might be causing problems.

This isolation approach is particularly effective when you suspect issues with agent-to-agent communication, configuration problems, or logic errors within specific agents.

## Examining STIM Files

STIM files serve as your detailed forensic evidence when debugging complex issues. These comprehensive traces capture every aspect of how requests flow through your system, making them invaluable for understanding problems that span multiple agents or involve timing-sensitive interactions.

[STIM files](./observability.md#examining-stimulus-logs) provide the most complete picture available of stimulus lifecycles. Unlike real-time monitoring tools that show current activity, STIM files preserve historical data that you can analyze repeatedly and share with team members for collaborative debugging.

Each `.stim` file contains a complete record of all Solace event broker events related to a single stimulus, from the initial user request through every agent interaction to the final response delivery. This comprehensive coverage makes STIM files particularly useful for debugging issues that involve:

- Multi-agent workflows where the problem might occur at any step
- Timing-related issues where sequence and duration matter
- Intermittent problems that are difficult to reproduce in real-time
- Performance bottlenecks that require detailed timing analysis

When examining STIM files, look for patterns in agent response times, unexpected message routing, or missing interactions that should have occurred based on your system design.

## Monitoring Event Broker Activity

Real-time Solace event broker monitoring provides immediate insights into your system's communication patterns and helps identify issues as they occur. This approach complements STIM file analysis by giving you live visibility into message flows and event interactions.

Broker-level monitoring is particularly valuable because it shows the actual communication happening between components, regardless of how agents are configured or what they report about their own status. This ground-truth perspective helps identify discrepancies between expected and actual behavior.

For comprehensive guidance on Solace event broker monitoring techniques and tools, see [Monitoring Event Broker Activity](./observability.md#monitoring-event-broker-activity).

## Using Debug Mode

Interactive debugging provides the deepest level of investigation capability by allowing you to pause execution and examine system state in real-time. Because Agent Mesh is built on Python, you can leverage standard Python debugging tools and IDE features to step through code execution and inspect variables.

This approach is most effective when you've already isolated the problem to specific components and need to understand exactly what's happening within agent logic or framework code.

### Setting Up VSCode Debugging

VSCode provides an excellent debugging environment for Agent Mesh development. The integrated debugger allows you to set breakpoints, step through code execution, and inspect variables in real-time, making it easier to understand complex agent interactions and identify logic errors.

Configure debugging by creating or updating your `.vscode/launch.json` file:

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

The `"justMyCode": false` setting is particularly important because it allows you to step into Agent Mesh framework code, not just your custom agent logic. This capability is valuable when debugging issues that might involve framework behavior or when you need to understand how your agents interact with the underlying platform.

To start a debugging session:

1. Open the **RUN AND DEBUG** panel in the left sidebar
2. Select `sam-debug` from the configuration dropdown
3. Click the **Play** button to launch your system in debug mode

Once running, you can set breakpoints in your agent code, framework files, or any Python modules your system uses. When execution hits a breakpoint, you can inspect variable states, evaluate expressions, and step through code line by line to understand exactly what's happening.

## Invoking Agents Directly

Direct agent invocation provides a powerful technique for isolating and testing individual agents outside of normal user workflows. This approach helps you verify that specific agents work correctly in isolation, making it easier to determine whether problems lie within agent logic or in the broader system interactions.

You can invoke agents directly through two primary methods: using the web UI's agent selection dropdown for quick testing, or sending messages directly through the Solace event broker for more controlled testing scenarios.

The Solace event broker-based approach gives you complete control over message content and timing, making it ideal for testing edge cases, error conditions, or specific message formats that might be difficult to generate through normal user interactions.

### Using Tools for Direct Message Testing

Several tools facilitate direct message testing, each suited to different debugging scenarios:

**[Solace Try Me VSCode Extension](https://marketplace.visualstudio.com/items?itemName=solace-tools.solace-try-me-vsc-extension)**: Integrates directly into your development environment, making it convenient to test messages without switching contexts. This tool is particularly useful during active development when you need to quickly verify agent behavior.

**[Solace Try Me (STM) CLI Tool](https://github.com/SolaceLabs/solace-tryme-cli)**: Provides command-line access for scripted testing and automation. This tool excels in scenarios where you need to send multiple test messages or integrate testing into automated workflows.

### Formatting Messages for Direct Invocation

Understanding the exact message format is crucial for successful direct agent testing. The following structure represents how the Agent Mesh framework expects messages to be formatted:

**Topic Structure**:
```
[NAME_SPACES]a2a/v1/agent/request/<agent_name>
```

Replace `<agent_name>` with the specific agent you want to test. The namespace prefix should match your system configuration.

**Required User Properties**:
```
userId: test-0000
clientId: test-0000
replyTo: [NAME_SPACES]a2a/v1/gateway/response/0000000/task-0000000
a2aUserConfig: {}
```

These properties provide essential context that agents expect, including user identification and response routing information.

**Message Payload**:
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

**Expected Response Topic**:
```
[NAME_SPACES]a2a/v1/gateway/response/0000000/task-0000000
```

Subscribe to this topic to receive the agent's response. The response will follow the same JSON-RPC format and contain the agent's output.

By sending carefully crafted requests and observing responses, you can verify agent behavior in complete isolation. This technique helps distinguish between agent-specific issues and broader system problems, significantly streamlining your debugging process.

## Analyzing System Logs

System logs serve as your comprehensive record of application behavior, capturing everything from routine operations to error conditions. These logs provide a different perspective than STIM files or Solace event broker monitoring—they focus on internal application state and framework behavior rather than message flows.

Understanding system logs becomes crucial when debugging issues related to agent initialization, configuration problems, or internal framework errors that might not be visible through other observability tools.

For detailed information about configuring system logs, see [Logging Configuration](./logging.md).
