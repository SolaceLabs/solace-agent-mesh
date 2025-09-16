---
title: SSO
sidebar_position: 10
---

## How to enable SSO

Before running the Docker container, create two configuration files for SSO under the root directory in your Named Docker Volume. Use the content provided below for each file:

<details>

<summary>Configuration files for SSO</summary>

**oauth2_server.yaml**
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
      config_file: "config/sso_vol/oauth2_config.yaml"
      host: ${OAUTH2_HOST, localhost}
      port: ${OAUTH2_PORT, 9000}
      ssl_cert: ""  # Optional: path to SSL certificate
      ssl_key: ""   # Optional: path to SSL private key

flows:
  # Initialize OAuth2 service
  - name: oauth2_service
    components:
      - component_name: oauth2_auth_service
        component_module: src.components.oauth2_component
        component_config:
          <<: *oauth2_config
```

**oauth2_config.yaml**

In the oauth2_config.yaml file, uncomment the authentication provider you want to use. 
Note that the Azure provider is configured as the default option.
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

</details>

## Running Solace Agent Mesh Enterprise with SSO enabled

Here is an example of Docker run command with Azure SSO provider for production use case:

:::tip
You may need to include `--platform linux/amd64` depending on the host machine you’re using.
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

You can then access Solace Agent Mesh Enterprise UI through http://localhost:8000

<details>

<summary>Configuration Options</summary>

**Specify the hostname and port for the UI running in the docker container. The main UI runs on port 8000 by default. Using 0.0.0.0 as the host allows external access to the container.**

```bash
-e FASTAPI_HOST="0.0.0.0" \
-e FASTAPI_PORT="8000" \ 
```

**Enable single sign-on processing on the frontend.**

```bash
-e FRONTEND_USE_AUTHORIZATION="true" \
```

**Specify the main URL of the UI. For instance, this could be https://www.example.com**

```bash
-e FRONTEND_REDIRECT_URL="http://localhost:8000" \
```

**Set the login URL used by the main UI. For instance, this could be https://www.example.com/api/v1/auth/login**

```bash
-e FRONTEND_AUTH_LOGIN_URL="http://localhost:8000/api/v1/auth/login" \
```

**Enable the OAUTH2 server and set the log level**

```bash
-e OAUTH2_ENABLED="true" \
-e OAUTH2_LOG_LEVEL="DEBUG" \
```

**Specify the hostname and port for the authorization server running in the docker container. Using 0.0.0.0 as the host allows external access to the container.**

```bash
-e OAUTH2_HOST="0.0.0.0" \
-e OAUTH2_PORT="9000" \
```

**Specify whether the Oauth2 checks use dev mode. When dev mode is true the following environment variables are added to allow http access and relax the token scope. This MUST be set false in a production environment.**

```bash
-e OAUTH2_DEV_MODE="true" \
```
```bash
OAUTHLIB_RELAX_TOKEN_SCOPE="1"
OAUTHLIB_INSECURE_TRANSPORT="1"
```

**Configure the environment variables for your chosen authentication provider. Refer to the oauth2_config.yaml file to identify the required variables. For example, with Azure set the following**

```bash
-e AZURE_TENANT_ID="xxxxxxxxx-xxxxxx-xxxxxxxx-xxxxxxxxxx" \
-e AZURE_CLIENT_ID="xxxxxxxxx-xxxxxx-xxxxxxxx-xxxxxxxxxx" \
-e AZURE_CLIENT_SECRET="xxxxxxxxx-xxxxxx-xxxxxxxx-xxxxxxxxxx" \
```

**Configure the authorization server's public URL (accessible from outside the Docker container) and specify the OAuth2 provider’s name from oauth2_config.yaml (this example uses the azure profile):**

```bash
-e EXTERNAL_AUTH_SERVICE_URL="http://localhost:9000" \
-e EXTERNAL_AUTH_PROVIDER="azure" \
```

**Lastly, set the callback URL that your auth provider will use to redirect with the auth code. For instance, this could be https://www.example.com/api/v1/auth/callback**

```bash
-e EXTERNAL_AUTH_CALLBACK="http://localhost:8000/api/v1/auth/callback" \
```

**Note that both the main UI and authorization server ports must be mapped to the host machine, as shown in the Docker run command above:**

```bash
-p 8000:8000 -p 9000:9000 \
```

**The oauth 2 configuration files must be mounted inside the container:**

```bash
-v <YOUR_NAMED_DOCKER_VOLUME>:/app/config/sso_vol/ \
```
</details>
