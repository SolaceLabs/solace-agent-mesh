# Solace Agent Mesh Configuration Reference

Complete configuration reference for Solace Agent Mesh, organized by topic for easy navigation.

## Quick Navigation

### Core Configuration
- **[Shared Configuration](./configs/shared-configuration.md)** - Centralized configuration using YAML anchors and reusable blocks
- **[Broker Configuration](./configs/broker-configuration.md)** - Solace PubSub+ Event Broker connection settings for A2A communication
- **[Model Configuration](./configs/model-configuration.md)** - LLM model definitions, providers, and parameters

### Component Configuration
- **[Agent Configuration](./configs/agent-configuration.md)** - Agent behavior, instructions, tools, and capabilities
- **[Gateway Configuration](./configs/gateway-configuration.md)** - Gateway configurations for WebUI, REST, Slack, and other interfaces
- **[Proxy Configuration](./configs/proxy-configuration.md)** - External agent proxy settings and authentication

### Tool & Service Configuration
- **[Tool Configuration](./configs/tool-configuration.md)** - Python tools, built-in tool groups, and MCP tool integration
- **[Service Configuration](./configs/service-configuration.md)** - Session storage, artifact storage, and data tools services
- **[Lifecycle Functions](./configs/lifecycle-functions.md)** - Agent initialization and cleanup function configuration

### Advanced Configuration
- **[Agent Card Configuration](./configs/agent-card-configuration.md)** - Agent metadata, capabilities, and discovery information
- **[Enterprise Configuration](./configs/enterprise-configuration.md)** - RBAC, SSO, trust manager, and enterprise features
- **[Environment Variables](./configs/environment-variables.md)** - Complete reference of environment variables

### Guidelines
- **[Best Practices](./configs/best-practices.md)** - Configuration best practices, patterns, and recommendations

## Configuration Overview

### What is Configured?

Solace Agent Mesh uses YAML-based configuration files to define:

1. **Agents** - AI agents with specific capabilities and tools
2. **Gateways** - Interfaces connecting external systems to the agent mesh
3. **Proxies** - Bridges to external agents and services
4. **Services** - Shared services like session storage and artifact management
5. **Tools** - Capabilities that agents can use to perform actions

### Configuration File Structure

```
project/
├── .env                          # Environment variables
├── configs/
│   ├── shared_config.yaml        # Shared configuration
│   ├── logging_config.yaml       # Logging configuration
│   ├── agents/
│   │   ├── agent1.yaml          # Agent configurations
│   │   └── agent2.yaml
│   ├── gateways/
│   │   ├── webui.yaml           # Gateway configurations
│   │   └── rest.yaml
│   └── plugins/
│       └── plugin1.yaml         # Plugin configurations
```

### Key Concepts

#### YAML Anchors
Shared configuration uses YAML anchors (`&anchor_name`) to create reusable blocks:

```yaml
shared_config:
  - broker_connection: &broker_connection
      broker_type: "solace"
      # ... broker settings

# Reference in agent config
components:
  - name: my-agent
    broker:
      <<: *broker_connection
```

#### Environment Variables
Sensitive data uses environment variables:

```yaml
broker_password: "${SOLACE_BROKER_PASSWORD}"
api_key: "${OPENAI_API_KEY}"
```

#### Configuration Hierarchy
1. **Shared Config** - Common settings for all components
2. **Component Config** - Specific agent/gateway settings
3. **Environment Variables** - Runtime values and secrets

## Getting Started

### For New Users
1. Start with [Shared Configuration](./configs/shared-configuration.md) to understand the foundation
2. Review [Broker Configuration](./configs/broker-configuration.md) for event mesh connectivity
3. Explore [Agent Configuration](./configs/agent-configuration.md) to create your first agent

### For Specific Tasks
- **Adding Tools**: See [Tool Configuration](./configs/tool-configuration.md)
- **Storage Setup**: See [Service Configuration](./configs/service-configuration.md)
- **Production Deployment**: See [Best Practices](./configs/best-practices.md)
- **Enterprise Features**: See [Enterprise Configuration](./configs/enterprise-configuration.md)

## Configuration Examples

### Minimal Agent Configuration

```yaml
!include shared_config.yaml

components:
  - name: simple-agent
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection
    app_config:
      namespace: "${NAMESPACE}"
      agent_name: "simple-agent"
      instruction: "You are a helpful assistant."
      model: *general_model
      session_service: *default_session_service
      artifact_service: *default_artifact_service
```

### Complete Agent with Tools

```yaml
!include shared_config.yaml

components:
  - name: advanced-agent
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection
    app_config:
      namespace: "${NAMESPACE}"
      agent_name: "advanced-agent"
      display_name: "Advanced Agent"
      
      instruction: |
        You are an advanced agent with multiple capabilities.
        Use your tools to help users effectively.
      
      model: *general_model
      
      tools:
        - tool_type: python
          component_module: "my_plugin.tools"
          function_name: "my_tool"
        
        - tool_type: builtin-group
          group_name: "artifact_management"
      
      session_service: *default_session_service
      artifact_service: *default_artifact_service
      
      agent_card:
        description: "Advanced agent with custom tools"
        defaultInputModes: ["text", "file"]
        defaultOutputModes: ["text", "file"]
```

## Additional Resources

- **Official Documentation**: https://solacelabs.github.io/solace-agent-mesh/
- **GitHub Repository**: https://github.com/SolaceLabs/solace-agent-mesh
- **LiteLLM Documentation**: https://docs.litellm.ai/
- **Solace PubSub+**: https://solace.com/products/event-broker/

## Version Information

This configuration reference is based on Solace Agent Mesh version 0.3.x. For the latest updates and changes, refer to the official documentation and release notes.