"""
Platform Service for Solace Agent Mesh.

ARCHITECTURE: Service vs Gateway
--------------------------------
SERVICES provide internal platform functionality (this component).
GATEWAYS handle external communication channels (http_sse, slack, webhook, etc.).

Platform Service Responsibilities:
- REST API for platform configuration management
- Agent Builder (CRUD operations on agents)
- Connector management (CRUD operations on connectors)
- Toolset discovery and management
- Deployment orchestration (deploy/update/undeploy agents)
- AI Assistant (AI-powered configuration help)
- Deployer heartbeat monitoring (track deployer availability)
- Background deployment status checking (verify agent deployments succeed)

Message Communication (Direct Messaging - Not A2A Protocol):
- PUBLISHES: Deployment commands (direct publishing) to deployer ({namespace}/deployer/agent/...)
- RECEIVES: Deployer heartbeats ({namespace}/deployer/heartbeat)
- RECEIVES: Agent cards for deployment monitoring ({namespace}/a2a/agent-cards)

What Platform Service is NOT:
- NOT a chat interface (no user sessions)
- NOT for task submission to agents (no orchestration of user tasks)
- NOT for artifact management (no chat artifacts or embeds)
- NOT for end-user communication (admin/platform operations only)
"""
