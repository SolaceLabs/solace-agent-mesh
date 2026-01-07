# Solace Agent Mesh Skills Documentation

This directory contains comprehensive skill documentation for creating and managing Solace Agent Mesh projects. These skills are designed to enable AI agents to guide users through the complete lifecycle of Agent Mesh development and deployment.

## Overview

Solace Agent Mesh is an open-source framework for building AI agent systems with event-driven architecture. These skills cover everything from initial setup to advanced production deployments.

## Skills Index

### 🚀 Getting Started

1. **[Initialize Project](skill-initialize-project.md)** (`initialize-agent-mesh-project`)
   - Set up new Agent Mesh projects
   - Configure broker connections and LLM services
   - Initialize storage and environment settings
   - **Start here for new projects**

2. **[Configure Shared Settings](skill-configure-shared-settings.md)** (`configure-shared-settings`)
   - Manage `shared_config.yaml` files
   - Configure broker connections and LLM models
   - Set up multi-environment configurations
   - Use YAML anchors and references

3. **[Run and Debug Projects](skill-run-and-debug-projects.md)** (`run-and-debug-projects`)
   - Execute Agent Mesh applications
   - Debug common issues
   - Monitor and troubleshoot
   - Production deployment strategies

### 🤖 Agent Development

4. **[Create and Manage Agents](skill-create-and-manage-agents.md)** (`create-and-manage-agents`)
   - Create specialized AI agents
   - Configure agent instructions and models
   - Set up agent cards and skills
   - Manage agent discovery and communication

5. **[Configure Agent Tools](skill-configure-agent-tools.md)** (`configure-agent-tools`)
   - Enable built-in tools
   - Create custom Python tools
   - Integrate MCP (Model Context Protocol) tools
   - Manage tool lifecycle

### 🌐 Integration

6. **[Create and Manage Gateways](skill-create-and-manage-gateways.md)** (`create-and-manage-gateways`)
   - Set up external interfaces (REST, SSE, Webhook)
   - Configure authentication and security
   - Integrate with Slack, Teams, Event Mesh
   - Manage system purpose and response formatting

7. **[Manage Plugins](skill-manage-plugins.md)** (`manage-plugins`)
   - Create reusable plugin components
   - Build and distribute plugins
   - Install and use community plugins
   - Share plugins across projects

### 🔧 Advanced Operations

8. **[Advanced Operations](skill-advanced-operations.md)** (`advanced-operations`)
   - Configure A2A proxies for remote agents
   - Set up evaluations and testing
   - Implement observability and monitoring
   - Deploy to Kubernetes
   - Configure security (RBAC, TLS)
   - Optimize performance

## Quick Start Guide

### For New Users

1. **Start with**: [Initialize Project](skill-initialize-project.md)
2. **Then**: [Create and Manage Agents](skill-create-and-manage-agents.md)
3. **Add capabilities**: [Configure Agent Tools](skill-configure-agent-tools.md)
4. **Expose to users**: [Create and Manage Gateways](skill-create-and-manage-gateways.md)
5. **Run and test**: [Run and Debug Projects](skill-run-and-debug-projects.md)

### For Experienced Users

- **Multi-environment setup**: [Configure Shared Settings](skill-configure-shared-settings.md)
- **Reusable components**: [Manage Plugins](skill-manage-plugins.md)
- **Production deployment**: [Advanced Operations](skill-advanced-operations.md)

## Skill Structure

Each skill document follows a consistent structure:

### 1. Header
- **Skill ID**: Unique identifier
- **Description**: What the skill covers
- **Prerequisites**: Required knowledge/setup
- **Related Skills**: Connected skills

### 2. Core Concepts
- Fundamental concepts explained
- Architecture diagrams
- Key terminology

### 3. Step-by-Step Instructions
- Multiple methods (GUI, CLI, automated)
- Complete examples
- Expected outputs

### 4. Common Patterns
- Real-world use cases
- Configuration templates
- Best practices

### 5. Troubleshooting
- Common issues and solutions
- Debugging techniques
- Validation steps

### 6. Reference
- Complete parameter tables
- Command syntax
- Configuration options

## Usage for AI Agents

These skills are designed to be used by AI agents to:

1. **Guide Users**: Provide step-by-step instructions
2. **Answer Questions**: Reference specific sections
3. **Troubleshoot Issues**: Use troubleshooting sections
4. **Recommend Patterns**: Suggest appropriate configurations
5. **Validate Setup**: Use checklists

### Example Agent Instructions

```
You are an expert in Solace Agent Mesh. Use the skills documentation to:
- Guide users through setup and configuration
- Provide accurate, detailed instructions
- Reference specific skill documents when needed
- Suggest best practices and patterns
- Help troubleshoot issues

Available skills:
- initialize-agent-mesh-project
- configure-shared-settings
- run-and-debug-projects
- create-and-manage-agents
- configure-agent-tools
- create-and-manage-gateways
- manage-plugins
- advanced-operations
```

## Key Concepts

### Agent Mesh Architecture

```
┌─────────────────────────────────────────────┐
│           External Systems                   │
│  (Users, APIs, Slack, Teams, Events)        │
└──────────────┬──────────────────────────────┘
               │
        ┌──────▼──────┐
        │  Gateways   │ (Entry Points)
        └──────┬──────┘
               │
        ┌──────▼──────────────────────┐
        │   Solace Event Broker       │ (Communication Backbone)
        │   (A2A Protocol)            │
        └──────┬──────────────────────┘
               │
        ┌──────▼──────┐
        │   Agents    │ (AI Processing)
        │   + Tools   │
        └──────┬──────┘
               │
        ┌──────▼──────────────────────┐
        │  Storage & Services         │
        │  (Sessions, Artifacts, DB)  │
        └─────────────────────────────┘
```

### Component Relationships

- **Agents**: AI-powered processing units with tools
- **Gateways**: External interfaces (REST, Slack, etc.)
- **Tools**: Capabilities (built-in, custom, MCP)
- **Broker**: Event mesh for communication
- **Storage**: Sessions, artifacts, data

### Configuration Hierarchy

```
Project Root
├── .env                          # Environment variables
├── configs/
│   ├── shared_config.yaml        # Shared settings
│   ├── agents/                   # Agent configurations
│   │   ├── agent1.yaml
│   │   └── agent2.yaml
│   └── gateways/                 # Gateway configurations
│       ├── gateway1.yaml
│       └── gateway2.yaml
└── src/                          # Custom code
    └── my_agent/
        ├── tools.py              # Custom tools
        └── lifecycle.py          # Lifecycle functions
```

## Common Workflows

### Workflow 1: Create Simple Chatbot

1. Initialize project with Web UI gateway
2. Create main orchestrator agent
3. Add built-in tools (artifact management)
4. Run and test via web interface

**Skills Used**: 
- `initialize-agent-mesh-project`
- `create-and-manage-agents`
- `run-and-debug-projects`

### Workflow 2: Data Analysis System

1. Initialize project
2. Create data analyst agent with SQL tools
3. Add custom data processing tools
4. Create REST gateway for API access
5. Deploy to production

**Skills Used**:
- `initialize-agent-mesh-project`
- `create-and-manage-agents`
- `configure-agent-tools`
- `create-and-manage-gateways`
- `advanced-operations`

### Workflow 3: Multi-Agent Collaboration

1. Initialize project
2. Create orchestrator agent
3. Create specialized agents (data, API, docs)
4. Configure inter-agent communication
5. Add Slack gateway
6. Monitor and optimize

**Skills Used**: All skills

## Best Practices

### Development
- ✅ Start with simple configurations
- ✅ Test incrementally
- ✅ Use version control
- ✅ Document custom components
- ✅ Follow naming conventions

### Configuration
- ✅ Use environment variables for secrets
- ✅ Leverage shared configuration
- ✅ Provide sensible defaults
- ✅ Comment YAML files
- ✅ Validate configurations

### Production
- ✅ Enable TLS everywhere
- ✅ Implement authentication
- ✅ Set up monitoring
- ✅ Configure backups
- ✅ Test disaster recovery

## Troubleshooting Guide

### Common Issues

| Issue | Skill Reference | Section |
|-------|----------------|---------|
| Can't connect to broker | `run-and-debug-projects` | Troubleshooting |
| Agent not responding | `create-and-manage-agents` | Troubleshooting |
| Tool not found | `configure-agent-tools` | Troubleshooting |
| Gateway won't start | `create-and-manage-gateways` | Troubleshooting |
| Plugin build fails | `manage-plugins` | Troubleshooting |

### Getting Help

1. **Check Troubleshooting Sections**: Each skill has detailed troubleshooting
2. **Review Examples**: Look at configuration examples
3. **Validate Setup**: Use validation checklists
4. **Check Logs**: Enable debug logging
5. **Consult Documentation**: Links provided in each skill

## Version Information

- **Skills Version**: 1.0.0
- **Compatible with**: Solace Agent Mesh 0.3.0+
- **Last Updated**: January 2026

## Contributing

These skills are designed to be:
- **Comprehensive**: Cover all major use cases
- **Accurate**: Based on official documentation
- **Practical**: Include working examples
- **Maintainable**: Easy to update

## Additional Resources

### Official Documentation
- [Solace Agent Mesh Docs](https://docs.cline.bot)
- [Getting Started Guide](https://docs.cline.bot/getting-started/getting-started)
- [API Reference](https://docs.cline.bot/components/components)

### Community
- [GitHub Repository](https://github.com/SolaceLabs/solace-agent-mesh)
- [Core Plugins](https://github.com/SolaceLabs/solace-agent-mesh-core-plugins)

### Related Technologies
- [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/)
- [Solace PubSub+](https://solace.com/products/event-broker/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

## License

These skill documents are provided as documentation for Solace Agent Mesh, which is licensed under the Apache License 2.0.

---

**Ready to get started?** Begin with [Initialize Project](skill-initialize-project.md) to create your first Agent Mesh application!