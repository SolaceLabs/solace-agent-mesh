"""
Platform Service for Solace Agent Mesh.

Provides REST API for platform configuration management:
- Agents
- Connectors
- Toolsets
- Deployments
- AI Assistant

This service is NOT a gateway - it does not:
- Manage chat sessions
- Submit tasks to agents via A2A
- Handle artifacts or embeds
- Communicate with the agent mesh

It only validates OAuth2 tokens and performs CRUD operations on platform data.
"""
