#!/usr/bin/env python3
"""
Standalone FastMCP server with OAuth authentication for testing
This isolates OAuth functionality from the Solace Agent Mesh integration
"""

import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth import OAuthProxy
import httpx
from fastmcp.server.auth import AccessToken, TokenVerifier

# Load environment variables from .env file
load_dotenv()

# Azure OAuth configuration - using your actual values
AZURE_TENANT_ID = "ce001ea4-74b1-40fc-9184-edb4a21a35d5"
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")

if not AZURE_CLIENT_ID or not AZURE_CLIENT_SECRET:
    print("❌ Error: AZURE_CLIENT_ID and AZURE_CLIENT_SECRET environment variables must be set")
    exit(1)

print(f"🔧 Configuring OAuth with Azure tenant: {AZURE_TENANT_ID}")
print(f"🔧 Client ID: {AZURE_CLIENT_ID}")

# Create a custom Azure token verifier that uses Microsoft Graph API like AzureProvider
class AzureGraphTokenVerifier(TokenVerifier):
    """Token verifier that validates Azure tokens via Microsoft Graph API"""
    
    def __init__(self, required_scopes=None, timeout_seconds=10):
        super().__init__(required_scopes=required_scopes)
        self.timeout_seconds = timeout_seconds
    
    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify Azure OAuth token by calling Microsoft Graph API."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                # Use Microsoft Graph API to validate token and get user info
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "User-Agent": "FastMCP-OAuth-Proxy-Azure",
                    },
                )

                if response.status_code != 200:
                    print(f"🔍 Azure token verification failed: {response.status_code} - {response.text[:200]}")
                    return None

                user_data = response.json()

                # Create AccessToken with Azure user info
                access_token = AccessToken(
                    token=token,
                    client_id=str(user_data.get("id", "unknown")),
                    scopes=self.required_scopes or [],
                    expires_at=None,
                    claims={
                        "sub": user_data.get("id"),
                        "email": user_data.get("mail") or user_data.get("userPrincipalName"),
                        "name": user_data.get("displayName"),
                        "given_name": user_data.get("givenName"),
                        "family_name": user_data.get("surname"),
                        "job_title": user_data.get("jobTitle"),
                        "office_location": user_data.get("officeLocation"),
                    },
                )
                print(f"🔍 Azure token verified successfully for user: {user_data.get('displayName')}")
                return access_token

        except httpx.RequestError as e:
            print(f"🔍 Failed to verify Azure token: {e}")
            return None
        except Exception as e:
            print(f"🔍 Azure token verification error: {e}")
            return None

# Create Azure token verifier using Graph API (like AzureProvider does)
token_verifier = AzureGraphTokenVerifier(
    required_scopes=["User.Read", "openid", "profile", "email"]
)

# Create the OAuth proxy with Azure Graph API token verification
auth = OAuthProxy(
    # Azure endpoints
    upstream_authorization_endpoint=f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/authorize",
    upstream_token_endpoint=f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token",
    
    # Your registered app credentials
    upstream_client_id=AZURE_CLIENT_ID,
    upstream_client_secret=AZURE_CLIENT_SECRET,
    
    # Token validation using Microsoft Graph API
    token_verifier=token_verifier,
    
    # Your FastMCP server URL
    base_url="http://localhost:3001",
    
    # Callback path - must match Azure app registration
    redirect_path="/mcp/auth/callback"
)

# Create FastMCP server with OAuth
mcp = FastMCP(name="OAuth Test Server", auth=auth)

# Add a simple test tool
@mcp.tool
async def test_tool(message: str) -> str:
    """A simple test tool that requires authentication."""
    from fastmcp.server.dependencies import get_access_token
    
    # Get the authenticated user's token
    token = get_access_token()
    if token and token.claims:
        user_name = token.claims.get("name", "Unknown User")
        user_email = token.claims.get("email", "No email")
        return f"Hello {user_name} ({user_email})! You sent: {message}"
    else:
        return f"Hello authenticated user! You sent: {message}"

# Add another test tool
@mcp.tool  
async def get_user_info() -> dict:
    """Get information about the authenticated user."""
    from fastmcp.server.dependencies import get_access_token
    
    token = get_access_token()
    if not token or not token.claims:
        return {"error": "No authentication token found"}
    
    return {
        "user_id": token.claims.get("sub"),
        "name": token.claims.get("name"),
        "email": token.claims.get("email"),
        "provider": "azure",
        "all_claims": dict(token.claims)
    }

# Add a tool to get the raw bearer token for MCP Inspector
@mcp.tool
async def get_bearer_token() -> dict:
    """Get the raw bearer token for use in MCP Inspector."""
    from fastmcp.server.dependencies import get_access_token
    
    token = get_access_token()
    if not token:
        return {"error": "No authentication token found"}
    
    return {
        "bearer_token": token.token,
        "instructions": "Copy the bearer_token value to MCP Inspector's 'Bearer Token' field",
        "user": token.claims.get("name", "Unknown") if token.claims else "Unknown"
    }

if __name__ == "__main__":
    print("🚀 Starting OAuth test server...")
    print("📋 Available tools:")
    print("  - test_tool: Simple echo with user info")  
    print("  - get_user_info: Returns authenticated user details")
    print()
    print("🔗 Azure App Registration should have redirect URI:")
    print("   http://localhost:3001/mcp/auth/callback")
    print()
    print("🧪 Test with:")
    print("   python test_oauth_client.py")
    print()
    
    # Run server on port 3001 to avoid conflicts
    mcp.run(transport="http", host="localhost", port=3001)