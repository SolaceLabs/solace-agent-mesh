"""
Shared utilities for Solace Agent Mesh.

This module contains utilities used by both gateways and services:
- API utilities (pagination, responses, auth)
- Database utilities (repositories, exceptions, helpers)
- Exception handling
- Common utilities (timestamps, enums, types)

Architecture:
- GATEWAYS (http_sse, slack, webhook) import from shared/
- SERVICES (platform) import from shared/
- No cross-dependencies between gateways and services
"""
