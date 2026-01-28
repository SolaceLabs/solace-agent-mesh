---
title: Authentication Proxy
sidebar_position: 12
---

# Authentication Proxy

Gateway OAuth enables apps and gateways (like MCP) to authenticate via the OAuth2 service without registering separate redirect URIs with OAuth providers. Apps redirect directly to the auth server, which handles the OAuth flow and returns a gateway code that can be exchanged for tokens.


## How It Works

High-level flow of the authentication proxy:

```mermaid
graph TD
    D[MCP Client<br> e.g. Claude Code] --> A;
    A[MCP Server Gateway<br>port 8090] --> B;
    B[OAuth2 Service<br>port 8080] --> C;
    C[OAuth Provider] --> B;
    B --> A;
    A --> D;
    linkStyle 0 stroke-width:2px,fill:none,stroke:white;
    linkStyle 1 stroke-width:2px,fill:none,stroke:white;
    linkStyle 2 stroke-width:2px,fill:none,stroke:white;
    linkStyle 3 stroke-width:2px,fill:none,stroke:grey;
    linkStyle 4 stroke-width:2px,fill:none,stroke:grey;
    linkStyle 5 stroke-width:2px,fill:none,stroke:grey;
```


Detailed sequence diagram of the OAuth2 authentication proxy flow:

```mermaid
sequenceDiagram
    participant MC as MCP Client
    participant UB as User Browser
    participant AG as MCP Server Gateway
    participant AS as Auth Server (OAuth2)
    participant OP as OAuth Provider

    MC->>+AG: 1. GET /.well-known/oauth-authorization-server
    AG-->>-MC: 2. Returns auth address

    MC->>UB: 3. Opens browser at auth URL
    Note right of MC: Includes redirect_uri and code params

    UB->>+AG: 4. GET /oauth/authorize
    AG-->>-UB: 5. Redirect: /login?gateway_uri=...

    Note over UB, AS: User is redirected to Auth Server
    UB->>+AS: Follows redirect
    AS-->>-UB: 6. Redirect to OAuth Provider

    Note over UB, OP: User is redirected to OAuth Provider
    UB->>+OP: Follows redirect
    OP-->>-UB: 7. User authenticates & grants consent

    Note over OP, AS: Provider redirects back to Auth Server with auth code
    OP->>+AS: 8. Redirect: /callback?code=...
    
    AS->>+OP: 9. Exchange authorization code for tokens
    OP-->>-AS: Returns access_token, refresh_token

    Note over AS, UB: Auth Server creates a gateway code and redirects to App
    AS-->>-UB: 10. Redirect: /oauth/callback?code=GATEWAY_CODE

    Note over UB, AG: User is redirected back to the App Gateway
    UB->>+AG: Follows redirect with GATEWAY_CODE
    
    AG->>+AS: 11. Exchange gateway code for tokens
    AS-->>-AG: Returns access_token, refresh_token
    AG-->>MC: 12. Return access_token to client
```

## Configuration
To enable the authentication proxy, add the following to your OAuth2 YAML configuration, usually named `oauth2_config.yaml`

```yaml
# This enables apps to redirect through this auth server for OAuth
proxy_oauth:
  enabled: true
  # Whitelist of allowed gateway callback URIs
  # Apps with URIs in this list can use this auth server for OAuth proxy
  allowed_redirect_uris:
    - "http://localhost:8090/oauth/callback"  # MCP gateway
    - "http://localhost:*"  # Wildcard for development - requires strict_uri_validation set to `false`
    - "https://mcp.example.com/oauth/callback"  # Production Example

  # Gateway code time-to-live in seconds (default: 300 = 5 minutes)
  # Codes expire after this time for security
  gateway_code_ttl_seconds: 300

  # URI validation mode (default: false = wildcard matching allowed)
  # Set to true for production to require exact URI matches
  strict_uri_validation: false
```

Update `allowed_redirect_uris` with the actual callback URIs of your gateways.

:::info
The path `/gateway-oauth` must be exposed and accessible in your deployment environment (e.g., Docker, Kubernetes) and it should point to the Auth Server service port.
:::

### Gateway Configuration

In your MCP Gateway configuration YAML (e.g. `my-mcp-gateway.yaml`), update the `adapter` section to enable OAuth and point to the Auth Server:

```yaml
adapter_config:
    enable_auth: ${OAUTH2_ENABLED}

    external_auth_service_url: ${EXTERNAL_AUTH_SERVICE_URL, http://localhost:8080}
    external_auth_provider: ${EXTERNAL_AUTH_PROVIDER, azure}
```