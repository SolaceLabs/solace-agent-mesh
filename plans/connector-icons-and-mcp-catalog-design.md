# Connector Icons & MCP Server Catalog — Design Notes

## 1. Connector Icon Field in Schema

### Problem
The builder agent creates connectors with generic subtypes (`api + openapi`), so the UI shows generic plug icons. The current frontend inference approach (matching connector names to known services) is fragile.

### Proposed Solution
Add an `icon` field to the connector config JSON schema that the LLM fills in from a known list of supported icons.

### Design

**Connector config JSON gets a new `icon` field:**
```json
{
  "type": "api",
  "subtype": "openapi",
  "icon": "jira",
  "values": { ... }
}
```

**The `icon` field is an enum with known values:**
- `jira`, `confluence`, `slack`, `github`, `gitlab`, `salesforce`, `servicenow`
- `pagerduty`, `zendesk`, `stripe`, `twilio`, `notion`, `hubspot`
- `trello`, `asana`, `linear`, `bitbucket`, `mongodb`, `elasticsearch`
- `snowflake`, `shopify`, `datadog`, `postgresql`, `mysql`, `redis`
- `other` (fallback — uses generic type-based icon)

**Builder agent instructions:**
- The `sam-connector-schema` skill documents the `icon` field with the full list of supported values
- The LLM picks the best match or uses `"other"` if the service isn't in the list
- The `ValidateComponentConfig` tool validates the icon value

**Frontend rendering:**
- `ConnectorCardNode` and `AgentCardNode` read `icon` from `connectorMetadata`
- Map icon values to SVG data URIs (reuse the existing `connectorIconInference.ts` icon map)
- No name-based inference needed — the icon is explicit in the config

### Changes Required
1. **Go backend**: Add `icon` to connector config schema validation (`builder_manifest_validate.go` or connector validation)
2. **`sam-connector-schema` skill**: Document the `icon` field with enum values
3. **`builderUtils.ts`**: Extract `icon` from connector JSON in `extractConnectorMetadata()`
4. **`ConnectorCardNode.tsx` / `AgentCardNode.tsx`**: Read `icon` from metadata, map to SVG
5. **`builder_agent.yaml`**: Reference the icon list in connector creation instructions

---

## 2. Curated MCP Server Catalog

### Problem
When users ask for connectors to specific services, the builder creates generic API connectors. For many services, there are known-good MCP servers that provide a better experience (proper tool schemas, authentication handling, etc.).

### Proposed Solution
Provide the builder agent with a curated catalog of recommended MCP servers for common services.

### Design

**New skill: `sam-mcp-catalog`**
A builder skill containing a catalog of known-good MCP servers:

```yaml
name: sam-mcp-catalog
description: Catalog of recommended MCP servers for common services
instruction_content: |
  ## MCP Server Catalog
  
  When the user needs to connect to one of these services, prefer using
  the recommended MCP server over a generic API connector.
  
  ### Jira
  - **MCP Server**: `@modelcontextprotocol/server-atlassian`
  - **Transport**: SSE
  - **URL**: `https://mcp.atlassian.com/v1/sse`
  - **Auth**: OAuth 2.0 (Atlassian Cloud)
  - **Tools**: search_issues, get_issue, create_issue, update_issue, ...
  - **Icon**: jira
  
  ### Confluence
  - **MCP Server**: `@modelcontextprotocol/server-atlassian`
  - **Transport**: SSE
  - **URL**: `https://mcp.atlassian.com/v1/sse`
  - **Auth**: OAuth 2.0 (Atlassian Cloud)
  - **Tools**: search_pages, get_page, create_page, ...
  - **Icon**: confluence
  
  ### GitHub
  - **MCP Server**: `@modelcontextprotocol/server-github`
  - **Transport**: stdio
  - **Auth**: Personal Access Token
  - **Tools**: search_repos, get_file, create_issue, ...
  - **Icon**: github
  
  ### Slack
  - **MCP Server**: `@modelcontextprotocol/server-slack`
  - **Transport**: stdio
  - **Auth**: Bot Token
  - **Tools**: send_message, list_channels, ...
  - **Icon**: slack
  
  ... (more services)
```

**Builder agent behavior:**
1. During Phase 1 discovery, when the user mentions a service (e.g., "I need to connect to Jira")
2. The builder loads `sam-mcp-catalog` to check if there's a recommended MCP server
3. If yes, proposes an MCP connector instead of a generic API connector
4. The connector config uses the recommended MCP server URL, transport, and auth method
5. The `icon` field is set from the catalog entry

### Changes Required
1. **New skill file**: `sam-mcp-catalog` with the curated catalog
2. **`builder_agent.yaml`**: Reference the catalog in Phase 1 discovery and Phase 3 connector creation
3. **Go backend**: Register the new skill
4. **Connector schema**: Ensure MCP connector configs support the catalog's auth methods

### Benefits
- Users get working connectors out of the box (no guessing MCP server URLs)
- Proper authentication flows (OAuth, API keys, etc.)
- Correct tool schemas (the MCP server provides them)
- Service-specific icons on the canvas
- Better UX than generic API connectors that might not work

---

## Priority
1. **Icon field in connector schema** — Medium priority, improves visual feedback
2. **MCP server catalog** — High priority, significantly improves connector quality

Both features complement each other — the catalog provides the icon value, and the schema validates it.
