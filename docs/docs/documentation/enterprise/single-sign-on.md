---
title: Enabling SSO
sidebar_position: 10
---

## Overview

Single Sign-On (SSO) enables users to authenticate with Agent Mesh Enterprise using their existing organizational credentials through OAuth2 providers such as Azure, Google, Auth0, Okta, or Keycloak. This integration eliminates the need for separate login credentials and leverages your organization's existing identity management infrastructure.

This guide walks you through configuring and enabling SSO for Agent Mesh Enterprise running in Docker. You will create configuration files, set up your OAuth2 provider, and launch the container with the appropriate environment variables.

## Prerequisites

Before you begin, ensure you have:

- A running instance of your chosen OAuth2 provider (Azure, Google, Auth0, Okta, Keycloak, or another OIDC-compliant provider)
- Client credentials (client ID and client secret) from your OAuth2 provider
- A Named Docker Volume for storing configuration files
- Access to the Agent Mesh Enterprise Docker image

## Understanding the SSO Architecture

Agent Mesh Enterprise uses a two-component architecture for SSO:

1. The main UI server (default port 8000) handles user interactions and serves the web interface
2. The OAuth2 authentication service (default port 9000) manages the authentication flow with your identity provider

When a user attempts to access the UI, they are redirected to your OAuth2 provider for authentication. After successful authentication, the provider redirects back to the application with an authorization code, which is then exchanged for access tokens. This separation of concerns keeps authentication logic isolated from the main application.

## Step 1: Create Configuration Files

You need to create two YAML configuration files in your Named Docker Volume. These files define how the OAuth2 service operates and which identity provider it connects to.

### Create oauth2_server.yaml

The oauth2_server.yaml file configures the OAuth2 authentication service as a component within Agent Mesh Enterprise. This file tells the system to start the OAuth2 service and specifies where to find its detailed configuration.

Create a file named `oauth2_server.yaml` in the root directory of your Named Docker Volume with the following content:

```yaml
---
# Example gateway configuration with OAuth2 service integration
# This shows how to configure a gateway to use the OAuth2 authentication service

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: oauth_server.log

!include ../shared_config.yaml

shared_config:
  # OAuth2 service configuration
  - oauth2_config: &oauth2_config
      enabled: true
      config_file: "configs/sso_vol/oauth2_config.yaml"
      host: ${OAUTH2_HOST, localhost}
      port: ${OAUTH2_PORT, 9000}
      ssl_cert: ""  # Optional: path to SSL certificate
      ssl_key: ""   # Optional: path to SSL private key

flows:
  # Initialize OAuth2 service
  - name: oauth2_service
    components:
      - component_name: oauth2_auth_service
        component_module: solace_agent_mesh_enterprise.components.oauth2_component
        component_config:
          <<: *oauth2_config
```

This configuration accomplishes several things:

- It sets up logging for the OAuth2 service, directing detailed debug information to oauth_server.log
- It references the shared_config.yaml file, which contains common configuration used across multiple components
- It defines the OAuth2 service configuration, including where to find the provider-specific settings (oauth2_config.yaml)
- It specifies the host and port where the OAuth2 service will listen for requests
- It creates a flow that initializes the OAuth2 authentication service component

The `${OAUTH2_HOST, localhost}` syntax means the service will use the OAUTH2_HOST environment variable if provided, otherwise it defaults to localhost. This pattern allows you to override configuration values at runtime without modifying the file.

### Create oauth2_config.yaml

The oauth2_config.yaml file contains provider-specific configuration for your chosen OAuth2 identity provider. This is where you specify which provider to use and provide the necessary credentials and endpoints.

Create a file named `oauth2_config.yaml` in the same directory with the following content:

```yaml
---
# OAuth2 Service Configuration
# This file configures the OAuth2 authentication service that supports multiple providers
# All providers now use the unified OIDC approach with automatic endpoint discovery

# Enable or disable the OAuth2 service
enabled: ${OAUTH2_ENABLED:false}

# Development mode - enables insecure transport and relaxed token scope for local development
# Set OAUTH2_DEV_MODE=true for local development (NEVER use in production!)
development_mode: ${OAUTH2_DEV_MODE:false}

# OAuth2 providers configuration
# All providers now use the unified OIDCProvider with automatic endpoint discovery
providers:
  # Google OAuth2 provider
  # google:
  #   # OIDC issuer URL - endpoints will be discovered automatically
  #   issuer: "https://accounts.google.com"
  #   client_id: ${GOOGLE_CLIENT_ID}
  #   client_secret: ${GOOGLE_CLIENT_SECRET}
  #   redirect_uri: ${GOOGLE_REDIRECT_URI:http://localhost:8080/callback}
  #   scope: "openid email profile"

  # Azure/Microsoft OAuth2 provider
  azure:
    # Azure OIDC issuer URL includes tenant ID
    issuer: https://login.microsoftonline.com/${AZURE_TENANT_ID}/v2.0
    client_id: ${AZURE_CLIENT_ID}
    client_secret: ${AZURE_CLIENT_SECRET}
    redirect_uri: ${AZURE_REDIRECT_URI:http://localhost:8080/callback}
    scope: "openid email profile offline_access"

  # Auth0 OAuth2 provider
  # auth0:
  #   # Auth0 issuer URL
  #   issuer: ${AUTH0_ISSUER:https://your-domain.auth0.com/}
  #   client_id: ${AUTH0_CLIENT_ID}
  #   client_secret: ${AUTH0_CLIENT_SECRET}
  #   redirect_uri: ${AUTH0_REDIRECT_URI:http://localhost:8080/callback}
  #   scope: "openid email profile"
  #   # Optional: Auth0 audience for API access
  #   audience: ${AUTH0_AUDIENCE:}

  # # Okta OAuth2 provider (example)
  # okta:
  #   issuer: ${OKTA_ISSUER:https://your-okta-domain.okta.com/oauth2/default}
  #   client_id: ${OKTA_CLIENT_ID}
  #   client_secret: ${OKTA_CLIENT_SECRET}
  #   redirect_uri: ${OKTA_REDIRECT_URI:http://localhost:8080/callback}
  #   scope: "openid email profile"

  # # Keycloak OAuth2 provider (example)
  # keycloak:
  #   issuer: ${KEYCLOAK_ISSUER:https://your-keycloak.com/auth/realms/your-realm}
  #   client_id: ${KEYCLOAK_CLIENT_ID}
  #   client_secret: ${KEYCLOAK_CLIENT_SECRET}
  #   redirect_uri: ${KEYCLOAK_REDIRECT_URI:http://localhost:8080/callback}
  #   scope: "openid email profile"

  # # Generic OIDC provider (for any standard OIDC-compliant provider)
  # custom_oidc:
  #   # Just provide the issuer URL and the service will discover all endpoints
  #   issuer: ${CUSTOM_OIDC_ISSUER:https://your-provider.com}
  #   client_id: ${CUSTOM_OIDC_CLIENT_ID}
  #   client_secret: ${CUSTOM_OIDC_CLIENT_SECRET}
  #   redirect_uri: ${CUSTOM_OIDC_REDIRECT_URI:http://localhost:8080/callback}
  #   scope: "openid email profile"

# Logging configuration
logging:
  level: ${OAUTH2_LOG_LEVEL:INFO}

# Session configuration
session:
  # Session timeout in seconds (default: 1 hour)
  timeout: ${OAUTH2_SESSION_TIMEOUT:3600}

# Security configuration
security:
  # CORS settings
  cors:
    enabled: ${OAUTH2_CORS_ENABLED:true}
    origins: ${OAUTH2_CORS_ORIGINS:*}

  # Rate limiting
  rate_limit:
    enabled: ${OAUTH2_RATE_LIMIT_ENABLED:true}
    requests_per_minute: ${OAUTH2_RATE_LIMIT_RPM:60}
```

This configuration file provides several important features:

The `enabled` setting controls whether the OAuth2 service is active. You can enable it by setting the OAUTH2_ENABLED environment variable to true.

The `development_mode` setting is crucial for local testing. When enabled, it allows HTTP connections (instead of requiring HTTPS) and relaxes token validation. You must disable this in production environments to maintain security.

The `providers` section defines multiple OAuth2 providers. By default, Azure is uncommented and active. To use a different provider, comment out the Azure section and uncomment your chosen provider. Each provider requires:

- An `issuer` URL that points to the OAuth2 provider's discovery endpoint
- A `client_id` and `client_secret` obtained from your provider's application registration
- A `redirect_uri` where the provider sends users after authentication
- A `scope` that defines what user information the application can access

The system uses OpenID Connect (OIDC) discovery, which means it automatically finds the authorization, token, and userinfo endpoints from the issuer URL. This simplifies configuration because you only need to provide the base issuer URL rather than individual endpoint URLs.

The `session` configuration determines how long authenticated sessions remain valid. The default of 3600 seconds (1 hour) balances security with user convenience.

The `security` section configures Cross-Origin Resource Sharing (CORS) and rate limiting. CORS allows the web UI to communicate with the OAuth2 service from different origins, while rate limiting prevents abuse by restricting the number of authentication requests per minute.

### Update Your WebUI Gateway

Update your WebUI Gateway to configure login as follows:

```
# Auth-related (placeholders, functionality depends on backend implementation)
frontend_auth_login_url: ${FRONTEND_AUTH_LOGIN_URL}
frontend_use_authorization: ${FRONTEND_USE_AUTHORIZATION}
frontend_redirect_url: ${FRONTEND_REDIRECT_URL, ""}

external_auth_callback_uri: ${EXTERNAL_AUTH_CALLBACK}
external_auth_service_url: ${EXTERNAL_AUTH_SERVICE_URL}
external_auth_provider: ${EXTERNAL_AUTH_PROVIDER}
```

Your final WebUI Gateway yaml configuration should look like this:

<details>

<summary>WebUI Gateway SSO Enabled</summary>

**webUI.yaml**
```yaml
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: webui_app.log


!include ../shared_config.yaml

apps:
  - name: a2a_webui_app
    app_base_path: .
    app_module: solace_agent_mesh.gateway.http_sse.app

    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      session_secret_key: "${SESSION_SECRET_KEY}"

      artifact_service: *default_artifact_service
      session_service: 
        type: "sql"
        database_url: ${WEB_UI_GATEWAY_DATABASE_URL, sqlite:///webui_gateway.db}
        default_behavior: "PERSISTENT"
      gateway_id: ${WEBUI_GATEWAY_ID}
      fastapi_host: ${FASTAPI_HOST}
      fastapi_port: ${FASTAPI_PORT}
      cors_allowed_origins: 
        - "http://localhost:3000" 
        - "http://127.0.0.1:3000"

      enable_embed_resolution: ${ENABLE_EMBED_RESOLUTION} # Enable late-stage resolution
      gateway_artifact_content_limit_bytes: ${GATEWAY_ARTIFACT_LIMIT_BYTES, 10000000} # Max size for late-stage embeds
      sse_max_queue_size: ${SSE_MAX_QUEUE_SIZE, 200} # Max size of SSE connection queues

      system_purpose: >
            The system is an AI Chatbot with agentic capabilities.
            It will use the agents available to provide information,
            reasoning and general assistance for the users in this system.
            **Always return useful artifacts and files that you create to the user.**
            Provide a status update before each tool call.
            Your external name is Agent Mesh.

      response_format: >
            Responses should be clear, concise, and professionally toned.
            Format responses to the user in Markdown using appropriate formatting.

      # --- Frontend Config Passthrough ---
      frontend_welcome_message: ${FRONTEND_WELCOME_MESSAGE}
      frontend_bot_name: ${FRONTEND_BOT_NAME}
      frontend_collect_feedback: ${FRONTEND_COLLECT_FEEDBACK}

      # Auth-related (placeholders, functionality depends on backend implementation)
      frontend_auth_login_url: ${FRONTEND_AUTH_LOGIN_URL}
      frontend_use_authorization: ${FRONTEND_USE_AUTHORIZATION}
      frontend_redirect_url: ${FRONTEND_REDIRECT_URL, ""}

      external_auth_callback_uri: ${EXTERNAL_AUTH_CALLBACK}
      external_auth_service_url: ${EXTERNAL_AUTH_SERVICE_URL}
      external_auth_provider: ${EXTERNAL_AUTH_PROVIDER}
```
</details>

## Step 2: Configure Your OAuth2 Provider

Before running the Docker container, you need to register an application with your chosen OAuth2 provider and obtain the necessary credentials.

### For Azure (Microsoft Entra ID)

1. Navigate to the Azure Portal and go to Microsoft Entra ID (formerly Azure Active Directory)
2. Select "App registrations" and create a new registration
3. Note the Application (client) ID and Directory (tenant) ID
4. Create a client secret under "Certificates & secrets"
5. Add a redirect URI pointing to your callback endpoint (for example, http://localhost:8000/api/v1/auth/callback)
6. Grant the necessary API permissions (typically Microsoft Graph with User.Read)

### For Google

1. Go to the Google Cloud Console and create a new project or select an existing one
2. Enable the Google+ API
3. Create OAuth2 credentials under "APIs & Services" > "Credentials"
4. Configure the authorized redirect URIs
5. Note the client ID and client secret

### For Other Providers

Consult your provider's documentation for application registration procedures. You will need to obtain a client ID, client secret, and configure the redirect URI to point to your Agent Mesh Enterprise callback endpoint.

## Step 3: Launch the Docker Container

With your configuration files in place and provider credentials obtained, you can now launch the Agent Mesh Enterprise container with SSO enabled.

The following example demonstrates a production deployment using Azure as the OAuth2 provider:

:::tip
You may need to include `--platform linux/amd64` depending on the host machine you're using.
:::

```bash
docker run -itd -p 8000:8000 -p 9000:9000 \
  -e LLM_SERVICE_API_KEY="<YOUR_LLM_TOKEN>" \
  -e LLM_SERVICE_ENDPOINT="<YOUR_LLM_SERVICE_ENDPOINT>" \
  -e LLM_SERVICE_PLANNING_MODEL_NAME="<YOUR_MODEL_NAME>" \
  -e LLM_SERVICE_GENERAL_MODEL_NAME="<YOUR_MODEL_NAME>" \
  -e NAMESPACE="<YOUR_NAMESPACE>" \
  -e SOLACE_DEV_MODE="false" \
  -e SOLACE_BROKER_URL="<YOUR_BROKER_URL>" \
  -e SOLACE_BROKER_VPN="<YOUR_BROKER_VPN>" \
  -e SOLACE_BROKER_USERNAME="<YOUR_BROKER_USERNAME>" \
  -e SOLACE_BROKER_PASSWORD="<YOUR_BROKER_PASSWORD>" \
  -e FASTAPI_HOST="0.0.0.0" \
  -e FASTAPI_PORT="8000" \
  -e AZURE_TENANT_ID="xxxxxxxxx-xxxxxx-xxxxxxxx-xxxxxxxxxx" \
  -e AZURE_CLIENT_ID="xxxxxxxxx-xxxxxx-xxxxxxxx-xxxxxxxxxx" \
  -e AZURE_CLIENT_SECRET="xxxxxxxxx-xxxxxx-xxxxxxxx-xxxxxxxxxx" \
  -e OAUTH2_ENABLED="true" \
  -e OAUTH2_LOG_LEVEL="DEBUG" \
  -e OAUTH2_DEV_MODE="true" \
  -e OAUTH2_HOST="0.0.0.0" \
  -e OAUTH2_PORT="9000" \
  -e FRONTEND_USE_AUTHORIZATION="true" \
  -e FRONTEND_REDIRECT_URL="http://localhost:8000" \
  -e FRONTEND_AUTH_LOGIN_URL="http://localhost:8000/api/v1/auth/login" \
  -e EXTERNAL_AUTH_SERVICE_URL="http://localhost:9000" \
  -e EXTERNAL_AUTH_PROVIDER="azure" \
  -e EXTERNAL_AUTH_CALLBACK="http://localhost:8000/api/v1/auth/callback" \
  -v <YOUR_NAMED_DOCKER_VOLUME>:/app/config/sso_vol/ \
  --name sam-ent-prod-sso \
solace-agent-mesh-enterprise:<tag> run config/sso_vol/oauth2_server.yaml config/webui_backend.yaml config/a2a_orchestrator.yaml config/a2a_agents.yaml
```

This command starts the container in detached mode with interactive terminal support. The `-p` flags expose both the main UI port (8000) and the OAuth2 service port (9000) to the host machine. The volume mount makes your configuration files available inside the container at the expected location.

After the container starts successfully, you can access the Agent Mesh Enterprise UI at http://localhost:8000. When you navigate to this URL, the system will redirect you to your OAuth2 provider's login page for authentication.

## Understanding the Environment Variables

The Docker run command includes numerous environment variables that control different aspects of the SSO configuration. Understanding these variables helps you customize the deployment for your specific environment.

### Core Application Settings

These variables configure the main Agent Mesh Enterprise application:

```bash
-e FASTAPI_HOST="0.0.0.0" \
-e FASTAPI_PORT="8000" \ 
```

The FASTAPI_HOST setting determines which network interfaces the main UI server binds to. Using "0.0.0.0" allows external access to the container, which is necessary for production deployments. The FASTAPI_PORT specifies which port the UI listens on inside the container.

### Frontend Authentication Settings

These variables control how the web UI handles authentication:

```bash
-e FRONTEND_USE_AUTHORIZATION="true" \
```

Setting FRONTEND_USE_AUTHORIZATION to "true" enables SSO processing on the frontend. When enabled, the UI will redirect unauthenticated users to the login flow instead of allowing direct access.

```bash
-e FRONTEND_REDIRECT_URL="http://localhost:8000" \
```

The FRONTEND_REDIRECT_URL specifies the main URL of your UI. In production, this would be your public-facing domain (for example, https://www.example.com). The system uses this URL to construct proper redirect chains during authentication.

```bash
-e FRONTEND_AUTH_LOGIN_URL="http://localhost:8000/api/v1/auth/login" \
```

The FRONTEND_AUTH_LOGIN_URL tells the frontend where to send users who need to authenticate. This endpoint initiates the OAuth2 flow by redirecting to your identity provider.

### OAuth2 Service Settings

These variables configure the OAuth2 authentication service itself:

```bash
-e OAUTH2_ENABLED="true" \
-e OAUTH2_LOG_LEVEL="DEBUG" \
```

The OAUTH2_ENABLED variable activates the OAuth2 service. Setting OAUTH2_LOG_LEVEL to "DEBUG" provides detailed logging information, which is helpful during initial setup and troubleshooting. You can change this to "INFO" or "WARNING" in production to reduce log verbosity.

```bash
-e OAUTH2_HOST="0.0.0.0" \
-e OAUTH2_PORT="9000" \
```

These variables specify where the OAuth2 authentication service listens for requests. Using "0.0.0.0" as the host allows external access to the container, which is necessary because the OAuth2 provider needs to reach the callback endpoint. The port must match the port mapping in your Docker run command.

```bash
-e OAUTH2_DEV_MODE="true" \
```

The OAUTH2_DEV_MODE setting controls whether the OAuth2 service operates in development mode. When set to "true", the service sets these internal environment variables:

```bash
OAUTHLIB_RELAX_TOKEN_SCOPE="1"
OAUTHLIB_INSECURE_TRANSPORT="1"
```

These settings allow HTTP connections (instead of requiring HTTPS) and relax token scope validation. This is convenient for local development and testing, but you must set OAUTH2_DEV_MODE to "false" in production environments to maintain security. Production deployments should always use HTTPS with valid SSL certificates.

### Provider-Specific Credentials

These variables provide the credentials obtained from your OAuth2 provider. The example shows Azure configuration:

```bash
-e AZURE_TENANT_ID="xxxxxxxxx-xxxxxx-xxxxxxxx-xxxxxxxxxx" \
-e AZURE_CLIENT_ID="xxxxxxxxx-xxxxxx-xxxxxxxx-xxxxxxxxxx" \
-e AZURE_CLIENT_SECRET="xxxxxxxxx-xxxxxx-xxxxxxxx-xxxxxxxxxx" \
```

The required variables depend on which provider you configured in oauth2_config.yaml. For Google, you would use GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET. For Auth0, you would use AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, and AUTH0_ISSUER. Refer to the oauth2_config.yaml file to identify the exact variable names for your chosen provider.

### External Authentication Configuration

These variables connect the main UI to the OAuth2 service:

```bash
-e EXTERNAL_AUTH_SERVICE_URL="http://localhost:9000" \
-e EXTERNAL_AUTH_PROVIDER="azure" \
```

The EXTERNAL_AUTH_SERVICE_URL specifies the public URL where the OAuth2 service can be reached. This must be accessible from outside the Docker container because your OAuth2 provider will redirect users to this service. The EXTERNAL_AUTH_PROVIDER must match one of the provider names defined in your oauth2_config.yaml file (in this example, "azure").

```bash
-e EXTERNAL_AUTH_CALLBACK="http://localhost:8000/api/v1/auth/callback" \
```

The EXTERNAL_AUTH_CALLBACK is the URL where your OAuth2 provider redirects users after successful authentication. This URL must be registered with your OAuth2 provider as an authorized redirect URI. In production, this would be your public domain followed by the callback path (for example, https://www.example.com/api/v1/auth/callback).

### Port Mapping and Volume Mount

Two additional configuration elements are essential for SSO to function:

```bash
-p 8000:8000 -p 9000:9000 \
```

Both the main UI port (8000) and the OAuth2 service port (9000) must be mapped to the host machine. This allows external access to both services, which is necessary for the authentication flow to complete successfully.

```bash
-v <YOUR_NAMED_DOCKER_VOLUME>:/app/config/sso_vol/ \
```

The volume mount makes your OAuth2 configuration files available inside the container at the expected location. Replace `<YOUR_NAMED_DOCKER_VOLUME>` with the path to your Named Docker Volume containing the oauth2_server.yaml and oauth2_config.yaml files.

## Verifying Your SSO Configuration

After starting the container, you can verify that SSO is working correctly:

1. Navigate to http://localhost:8000 in your web browser
2. You should be automatically redirected to your OAuth2 provider's login page
3. After entering your credentials, you should be redirected back to the Agent Mesh Enterprise UI
4. Check the container logs for any authentication errors: `docker logs sam-ent-prod-sso`

If you encounter issues, check that:

- Your OAuth2 provider credentials are correct
- The redirect URI in your provider's configuration matches the EXTERNAL_AUTH_CALLBACK value
- Both ports (8000 and 9000) are accessible from your network
- The configuration files are properly mounted in the container

## Understanding the OAuth2 Flow and Environment Variables

When using SSO, it’s important to understand how the authentication flow works between the WebUI Gateway, the OAuth2 service, and your identity provider (IdP). This section clarifies the purpose of each variable and common configuration mistakes.

### How the OAuth2 Flow Works

1. A user opens the frontend application (for example, `http://localhost:8000`).  
   - The frontend checks whether a valid access token exists (e.g., in local storage or cookies).  
   - If no valid token is found or the token has expired, the frontend automatically calls the backend endpoint defined by `FRONTEND_AUTH_LOGIN_URL` (for example, `http://localhost:8000/api/v1/auth/login`) to start the authentication process.  
2. The WebUI Gateway calls the `EXTERNAL_AUTH_SERVICE_URL` (typically `http://localhost:9000`) and passes the `EXTERNAL_AUTH_PROVIDER` value (such as `azure` or `keycloak` or `auth0`, or `google`).
3. The OAuth2 service looks up the provider in `oauth2_config.yaml` and automatically constructs the correct authorization request using the provider’s `issuer`, `client_id`, `redirect_uri`, and `scope`.
4. The user is redirected to the IdP (e.g., Azure AD, Auth0, or Keycloak) for login.
5. After successful login, the IdP redirects back to `EXTERNAL_AUTH_CALLBACK` (for example, `http://localhost:8000/api/v1/auth/callback`).
6. The OAuth2 service exchanges the authorization code for tokens and finalizes authentication.

> **Note:**  
> You do *not* need to manually append `client_id`, `scope`, or `redirect_uri` query parameters to the login URL.  
> The OAuth2 service automatically handles these based on the selected provider in `oauth2_config.yaml`.

### Common Environment Variables

| Variable | Purpose | Example |
|-----------|----------|----------|
| `FRONTEND_AUTH_LOGIN_URL` | The frontend endpoint that triggers authentication. It should **not** include OAuth query parameters. | `http://localhost:8000/api/v1/auth/login` |
| `EXTERNAL_AUTH_SERVICE_URL` | URL of the OAuth2 authentication service. | `http://localhost:9000` |
| `EXTERNAL_AUTH_PROVIDER` | The IdP name as defined under `providers:` in `oauth2_config.yaml`. | `azure` or `keycloak` |
| `EXTERNAL_AUTH_CALLBACK` | Callback URI used after login. Must match the redirect URI registered with your IdP. | `http://localhost:8000/api/v1/auth/callback` |
| `FRONTEND_REDIRECT_URL` | Where users are redirected after login completes. | `http://localhost:8000` |

## Security Considerations for Production

When deploying SSO in a production environment, follow these security best practices:

Set OAUTH2_DEV_MODE to "false" to disable insecure transport and enforce proper token validation. This ensures that all OAuth2 communication uses HTTPS with valid SSL certificates.

Use HTTPS for all URLs (FRONTEND_REDIRECT_URL, FRONTEND_AUTH_LOGIN_URL, EXTERNAL_AUTH_SERVICE_URL, and EXTERNAL_AUTH_CALLBACK). Configure SSL certificates using the ssl_cert and ssl_key parameters in oauth2_server.yaml.

Restrict CORS origins by setting OAUTH2_CORS_ORIGINS to your specific domain instead of using the wildcard "*". This prevents unauthorized websites from making requests to your authentication service.

Regularly rotate your OAuth2 client secrets and update the corresponding environment variables. Store sensitive credentials securely using Docker secrets or a secrets management service rather than passing them directly in the command line.

Configure appropriate session timeouts based on your security requirements. Shorter timeouts increase security but may inconvenience users who need to reauthenticate more frequently.

Monitor authentication logs for suspicious activity and failed login attempts. The OAuth2 service logs all authentication events, which you can review for security auditing.
