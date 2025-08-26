# SAM MCP Gateway OAuth Integration Plan

## Overview
Implement OAuth 2.1 authentication for SAM MCP Gateway following the MCP specification, integrating with Azure AD for enterprise identity management.

## Prerequisites
- Basic MCP Gateway functionality working (Phase 1 from main plan)
- Azure AD tenant with admin access
- SAM deployed and accessible

## Azure AD Setup

### 1. Azure AD App Registration
Create a single Azure AD application for organizational MCP access:

**App Settings:**
- **Name**: "SAM MCP Access"
- **Account Type**: Single tenant (your organization)
- **Platform**: Public client/native (desktop apps)
- **Redirect URIs**: 
  - `http://localhost:3000/callback` (Claude Desktop)
  - `http://localhost:8080/callback` (VS Code)
  - Additional ports as needed for MCP clients

**API Permissions:**
- Microsoft Graph: `User.Read` (basic profile)
- Custom SAM API scopes (if needed)

**Authentication:**
- Enable public client flows (PKCE)
- No client secret required
- Token lifetime: Default (1 hour access, 90 days refresh)

### 2. Custom Scopes (Optional)
Define SAM-specific scopes in Azure AD:
- `sam.agent.delegate` - Can call agents
- `sam.agent.discover` - Can list available agents
- `sam.agent.admin` - Full administrative access

### 3. Role Assignment
Map Azure AD roles to SAM permissions:
- **SAM Agent User** → `sam.agent.delegate`, `sam.agent.discover`
- **SAM Agent Admin** → `sam.agent.*`

## SAM MCP Gateway Implementation

### 1. OAuth Capability Advertisement
MCP server must advertise OAuth capabilities:

```json
{
  "capabilities": {
    "authorization": {
      "authorization_endpoint": "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
      "token_endpoint": "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
      "client_id": "{azure_app_client_id}",
      "scopes": ["sam.agent.delegate", "sam.agent.discover"],
      "audience": "api://sam-mcp-access"
    }
  }
}
```

### 2. Token Validation Pipeline
Implement token validation in MCP gateway:

**Steps:**
1. Extract bearer token from MCP request headers
2. Validate token signature against Azure AD JWKS
3. Verify token audience and issuer
4. Extract user claims (email, roles, etc.)
5. Map Azure AD roles to SAM permissions
6. Enrich user context for A2A task submission

**Token Validation Service:**
- Use Azure AD JWKS endpoint for signature verification
- Cache JWKS keys with appropriate TTL
- Handle token expiry and refresh scenarios
- Log authentication events for audit

### 3. User Identity Integration
Map OAuth tokens to SAM user context:

**User Profile Extraction:**
- Email from `preferred_username` or `email` claim
- Display name from `name` claim
- Roles from `roles` claim (if using App Roles)
- Organization from `tid` claim

**Permission Mapping:**
- Azure AD roles → SAM permission strings
- Configurable mapping in gateway config
- Default permissions for authenticated users
- Admin override capabilities

## Configuration

### 1. MCP Gateway Configuration
```yaml
apps:
  - name: mcp_gateway_app
    app_config:
      mcp_transport: "stdio"
      agent_discovery_interval: 60
      
      # OAuth Configuration
      oauth:
        enabled: true
        azure_tenant_id: "${AZURE_TENANT_ID}"
        client_id: "${AZURE_CLIENT_ID}"
        audience: "api://sam-mcp-access"
        jwks_cache_ttl: 3600  # 1 hour
        
        # Role mapping
        role_permissions:
          "SAM.Agent.User": ["delegate", "discover"]
          "SAM.Agent.Admin": ["delegate", "discover", "admin"]
        
        # Default permissions for authenticated users
        default_permissions: ["discover"]
```

### 2. Environment Variables
```bash
# Azure AD Configuration
AZURE_TENANT_ID="12345678-1234-1234-1234-123456789012"
AZURE_CLIENT_ID="87654321-4321-4321-4321-210987654321"

# Optional: Custom authority endpoint
AZURE_AUTHORITY="https://login.microsoftonline.com/${AZURE_TENANT_ID}"
```

## MCP Client Configuration

### 1. Claude Desktop
```json
{
  "mcpServers": {
    "sam": {
      "command": "sam-mcp-server",
      "args": ["--config", "mcp_gateway.yaml"],
      "env": {
        "AZURE_TENANT_ID": "12345678-1234-1234-1234-123456789012",
        "AZURE_CLIENT_ID": "87654321-4321-4321-4321-210987654321"
      }
    }
  }
}
```

### 2. VS Code Extension
Similar configuration through VS Code settings or extension-specific config files.

## Implementation Steps

### Phase 1: Basic OAuth Support
1. **Add OAuth capability advertisement** to MCP server metadata
2. **Implement token validation** service using Azure AD JWKS
3. **Create user identity extraction** from validated tokens
4. **Add OAuth configuration** to gateway YAML
5. **Test with Claude Desktop** OAuth flow

### Phase 2: Enhanced Features
1. **Role-based permissions** enforcement
2. **Token refresh handling** for long-running sessions
3. **Audit logging** for OAuth authentication events
4. **Error handling** for common OAuth scenarios
5. **Multi-tenant support** (if needed)

### Phase 3: Production Readiness
1. **Security hardening** (rate limiting, token validation)
2. **Monitoring and metrics** for OAuth usage
3. **Documentation** for IT administrators
4. **Troubleshooting guides** for common issues

## User Experience Flow

### First-Time Setup
1. **IT Admin** creates Azure AD app and configures SAM MCP Gateway
2. **User** configures Claude Desktop with SAM MCP server
3. **First MCP tool call** → Claude Desktop opens browser for OAuth
4. **User logs in** with corporate Azure AD credentials
5. **Claude Desktop stores token** and completes original request

### Ongoing Usage
1. **All MCP calls** automatically include stored OAuth token
2. **Token refresh** handled transparently by Claude Desktop
3. **No user intervention** required unless token is revoked

## Security Considerations

### Token Security
- Use short-lived access tokens (1 hour default)
- Implement proper token audience validation
- Cache JWKS keys securely with appropriate TTL
- Log all authentication attempts

### Network Security
- Require HTTPS for all OAuth endpoints
- Validate redirect URIs to prevent open redirects
- Implement rate limiting on token validation

### Audit and Compliance
- Log all MCP calls with user identity
- Track permission usage and escalation
- Integrate with existing SAM audit systems
- Support compliance reporting requirements

## Troubleshooting

### Common Issues
1. **Token validation failures** - Check JWKS endpoint accessibility
2. **Permission denied** - Verify Azure AD role assignments
3. **OAuth flow failures** - Check redirect URI configuration
4. **Token expiry** - Ensure proper refresh token handling

### Debugging Tools
- Token validation endpoint for testing
- OAuth flow diagnostic logging
- Permission mapping verification tools
- Network connectivity tests

## Future Enhancements

### Advanced Features
- **Conditional Access** integration with Azure AD policies
- **Multi-factor authentication** enforcement
- **Device compliance** checking
- **Just-in-time access** for elevated permissions

### Integration Opportunities
- **Microsoft Graph** integration for user profile enrichment
- **Azure Key Vault** for configuration secrets
- **Azure Monitor** for authentication metrics
- **Microsoft Sentinel** for security event correlation

This OAuth integration provides enterprise-grade authentication while maintaining the seamless user experience expected from MCP tools.