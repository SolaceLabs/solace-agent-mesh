# Skill: Configure Agent Tools in Solace Agent Mesh

## Skill ID
`configure-agent-tools`

## Description
Configure and manage tools for Solace Agent Mesh agents, including built-in tools, custom Python tools, and MCP (Model Context Protocol) integrations. This skill covers tool types, configuration patterns, lifecycle management, and best practices for extending agent capabilities.

## Prerequisites
- Created agent (see `skill-create-and-manage-agents`)
- Understanding of Python programming (for custom tools)
- Familiarity with agent configuration YAML

## Related Skills
- `create-and-manage-agents` - Agent creation and management
- `manage-plugins` - Plugin-based tool distribution
- `configure-shared-settings` - Shared configuration management

---

## Core Concepts

### What are Tools?

Tools are specific capabilities that agents can use to accomplish tasks. They enable agents to:

1. **Access Data**: Query databases, read files, fetch from APIs
2. **Transform Data**: Process, analyze, and visualize information
3. **Generate Content**: Create images, audio, documents
4. **Communicate**: Make web requests, send messages
5. **Manage Artifacts**: Create, read, update files

### Tool Types

Agent Mesh supports three primary tool types:

| Type | Description | Use Case |
|------|-------------|----------|
| **Built-in Tools** | Pre-packaged tools from the framework | Standard operations (files, data, web) |
| **Custom Python Tools** | Your own Python functions | Business logic, proprietary systems |
| **MCP Tools** | External tool servers via MCP protocol | Language-agnostic, standalone services |

### Tool Architecture

```
┌──────────────────────────────────┐
│          Agent                    │
│  ┌────────────────────────────┐  │
│  │     Tool Registry          │  │
│  ├────────────────────────────┤  │
│  │  • Built-in Tools          │  │
│  │  • Custom Python Tools     │  │
│  │  • MCP Tools               │  │
│  └────────────────────────────┘  │
│              │                    │
│              ├──> LLM decides     │
│              │    which tool      │
│              └──> Tool executes   │
└──────────────────────────────────┘
```

---

## Built-in Tools

### Available Tool Groups

Agent Mesh provides organized tool groups:

| Group Name | Tools Included | Use Case |
|------------|----------------|----------|
| `artifact_management` | File operations, artifact handling | Create, read, manage files |
| `data_analysis` | SQL queries, data transformation, charts | Analyze and visualize data |
| `web` | HTTP requests | Call external APIs |
| `audio` | Text-to-speech, transcription | Audio processing |
| `image` | Image generation, analysis | Image operations |
| `general` | File conversion, diagrams | Utility functions |

### Enable Tool Groups

#### Method 1: Enable Entire Group (Recommended)

```yaml
tools:
  # Enable all artifact management tools
  - tool_type: builtin-group
    group_name: "artifact_management"
  
  # Enable all data analysis tools
  - tool_type: builtin-group
    group_name: "data_analysis"
  
  # Enable web request tools
  - tool_type: builtin-group
    group_name: "web"
```

#### Method 2: Enable Individual Tools

```yaml
tools:
  # Enable specific tool from a group
  - tool_type: builtin
    tool_name: "web_request"
  
  - tool_type: builtin
    tool_name: "query_data_with_sql"
  
  - tool_type: builtin
    tool_name: "create_chart_from_plotly_config"
```

### Built-in Tool Reference

#### Artifact Management Tools

```yaml
- tool_type: builtin-group
  group_name: "artifact_management"
```

**Included Tools:**
- `append_to_artifact`: Append content to existing artifacts
- `list_artifacts`: List available artifacts
- `load_artifact`: Load artifact content
- `apply_embed_and_create_artifact`: Create artifacts with embedded content
- `extract_content_from_artifact`: Extract content from artifacts

**Use Cases:**
- File management
- Document storage
- Data persistence

---

#### Data Analysis Tools

```yaml
- tool_type: builtin-group
  group_name: "data_analysis"
```

**Included Tools:**
- `query_data_with_sql`: Execute SQL queries
- `create_sqlite_db`: Create SQLite databases
- `transform_data_with_jq`: Transform JSON with jq
- `create_chart_from_plotly_config`: Generate Plotly charts

**Use Cases:**
- Database queries
- Data transformation
- Visualization

**Configuration:**
```yaml
- tool_type: builtin-group
  group_name: "data_analysis"
  tool_config:
    sqlite_memory_threshold_mb: 100
    max_result_preview_rows: 50
```

---

#### Web Tools

```yaml
- tool_type: builtin-group
  group_name: "web"
```

**Included Tools:**
- `web_request`: Make HTTP requests (GET, POST, PUT, DELETE)

**Use Cases:**
- API calls
- Web scraping
- External service integration

---

#### Audio Tools

```yaml
- tool_type: builtin-group
  group_name: "audio"
```

**Included Tools:**
- `text_to_speech`: Convert text to audio
- `multi_speaker_text_to_speech`: Multi-speaker audio generation
- `transcribe_audio`: Transcribe audio to text

**Use Cases:**
- Voice generation
- Audio transcription
- Accessibility features

---

#### Image Tools

```yaml
- tool_type: builtin-group
  group_name: "image"
```

**Included Tools:**
- `create_image_from_description`: Generate images from text
- `describe_image`: Analyze and describe images
- `edit_image_with_gemini`: Edit images using Gemini
- `describe_audio`: Describe audio content

**Use Cases:**
- Image generation
- Image analysis
- Visual content creation

---

#### General Tools

```yaml
- tool_type: builtin-group
  group_name: "general"
```

**Included Tools:**
- `convert_file_to_markdown`: Convert files to markdown
- `mermaid_diagram_generator`: Generate Mermaid diagrams

**Use Cases:**
- Document conversion
- Diagram generation

---

### List Available Built-in Tools

Use the CLI to discover tools:

```bash
# List all built-in tools
sam tools list

# List tools in specific category
sam tools list --category artifact_management

# Show detailed information
sam tools list --detailed

# Output as JSON
sam tools list --json
```

---

## Custom Python Tools

### Tool Creation Patterns

#### Pattern 1: Simple Function-Based Tool

**Use Case:** Quick, straightforward tools

**Create Tool File** (`src/my_agent/tools.py`):

```python
from typing import Any, Dict, Optional
from google.adk.tools import ToolContext
from solace_ai_connector.common.log import log

async def calculate_discount(
    price: float,
    discount_percent: float,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculate discounted price.
    
    Args:
        price: Original price
        discount_percent: Discount percentage (0-100)
    
    Returns:
        Dictionary with original price, discount, and final price
    """
    log.info(f"Calculating {discount_percent}% discount on ${price}")
    
    discount_amount = price * (discount_percent / 100)
    final_price = price - discount_amount
    
    return {
        "original_price": price,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "final_price": final_price
    }
```

**Configure in YAML:**

```yaml
tools:
  - tool_type: python
    component_module: "my_agent.tools"
    function_name: "calculate_discount"
    component_base_path: "src"
```

---

#### Pattern 2: Tool with Configuration

**Use Case:** Tools that need API keys or settings

**Create Tool:**

```python
async def fetch_weather(
    city: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Fetch weather data for a city.
    
    Args:
        city: City name
    
    Returns:
        Weather information
    """
    # Get API key from tool_config
    api_key = tool_config.get("api_key") if tool_config else None
    if not api_key:
        return {"error": "API key not configured"}
    
    # Use API key to fetch weather
    # ... implementation
    
    return {"city": city, "temperature": 72, "conditions": "sunny"}
```

**Configure with API Key:**

```yaml
tools:
  - tool_type: python
    component_module: "my_agent.tools"
    function_name: "fetch_weather"
    component_base_path: "src"
    tool_config:
      api_key: ${WEATHER_API_KEY}
```

---

#### Pattern 3: DynamicTool Class

**Use Case:** Complex tools with programmatic interfaces

**Create Tool:**

```python
from google.genai import types as adk_types
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool
from pydantic import BaseModel, Field

class WeatherConfig(BaseModel):
    """Configuration for weather tool."""
    api_key: str = Field(description="Weather API key")
    default_units: str = Field(default="celsius")

class WeatherTool(DynamicTool):
    """Dynamic weather tool with validated config."""
    
    config_model = WeatherConfig
    
    @property
    def tool_name(self) -> str:
        return "get_weather"
    
    @property
    def tool_description(self) -> str:
        return f"Get weather data. Default units: {self.tool_config.default_units}"
    
    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "city": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="City name"
                ),
                "units": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    enum=["celsius", "fahrenheit"],
                    nullable=True
                )
            },
            required=["city"]
        )
    
    async def _run_async_impl(self, args: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        city = args["city"]
        units = args.get("units", self.tool_config.default_units)
        
        # Use self.tool_config.api_key
        # ... implementation
        
        return {"city": city, "temperature": 72, "units": units}
```

**Configure:**

```yaml
tools:
  - tool_type: python
    component_module: "my_agent.weather_tools"
    class_name: "WeatherTool"
    component_base_path: "src"
    tool_config:
      api_key: ${WEATHER_API_KEY}
      default_units: "fahrenheit"
```

---

#### Pattern 4: DynamicToolProvider (Tool Factory)

**Use Case:** Generate multiple related tools from one configuration

**Create Provider:**

```python
from typing import List
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicToolProvider
from pydantic import BaseModel, Field

class DatabaseConfig(BaseModel):
    """Configuration for database tools."""
    connection_string: str = Field(description="Database connection string")
    max_rows: int = Field(default=1000)

class DatabaseToolProvider(DynamicToolProvider):
    """Provider that creates multiple database tools."""
    
    config_model = DatabaseConfig
    
    def create_tools(self, tool_config: DatabaseConfig) -> List[DynamicTool]:
        """Create all database tools."""
        return [
            QueryTool(tool_config=tool_config),
            SchemaTool(tool_config=tool_config),
            ExportTool(tool_config=tool_config)
        ]

# Register simple function as tool
@DatabaseToolProvider.register_tool
async def get_db_version(tool_config: dict, **kwargs) -> dict:
    """Get database version."""
    # ... implementation
    return {"version": "PostgreSQL 15.3"}
```

**Configure:**

```yaml
tools:
  # Single configuration creates multiple tools
  - tool_type: python
    component_module: "my_agent.database_tools"
    component_base_path: "src"
    tool_config:
      connection_string: ${DATABASE_URL}
      max_rows: 5000
```

---

### Tool Lifecycle Management

#### YAML-Based Lifecycle Hooks

**Use Case:** Initialize/cleanup resources for any tool

**Create Lifecycle Functions:**

```python
# src/my_agent/tools.py
from solace_agent_mesh.agent.sac.component import SamAgentComponent
from solace_agent_mesh.agent.tools.tool_config_types import AnyToolConfig

async def initialize_db_connection(
    component: SamAgentComponent,
    tool_config_model: AnyToolConfig
):
    """Initialize database connection."""
    log.info("Initializing database connection...")
    
    conn_string = tool_config_model.tool_config.get("connection_string")
    db_client = create_db_client(conn_string)
    
    # Store in agent state
    component.set_agent_specific_state("db_client", db_client)
    
    log.info("Database connection initialized")

async def close_db_connection(
    component: SamAgentComponent,
    tool_config_model: AnyToolConfig
):
    """Close database connection."""
    log.info("Closing database connection...")
    
    db_client = component.get_agent_specific_state("db_client")
    if db_client:
        await db_client.close()
    
    log.info("Database connection closed")

async def query_database(
    query: str,
    tool_context: ToolContext,
    **kwargs
) -> Dict[str, Any]:
    """Query database using initialized connection."""
    host_component = tool_context._invocation_context.agent.host_component
    db_client = host_component.get_agent_specific_state("db_client")
    
    if not db_client:
        return {"error": "Database not initialized"}
    
    results = await db_client.execute(query)
    return {"results": results}
```

**Configure with Lifecycle:**

```yaml
tools:
  - tool_type: python
    component_module: "my_agent.tools"
    function_name: "query_database"
    component_base_path: "src"
    init_function: "initialize_db_connection"
    cleanup_function: "close_db_connection"
    tool_config:
      connection_string: ${DATABASE_URL}
```

---

#### Class-Based Lifecycle Methods

**Use Case:** Encapsulated lifecycle in DynamicTool

**Create Tool with Lifecycle:**

```python
class DatabaseTool(DynamicTool):
    """Tool with built-in lifecycle management."""
    
    async def init(self, component: SamAgentComponent, tool_config: AnyToolConfig):
        """Initialize on agent startup."""
        log.info("Initializing database tool...")
        self.db_client = create_db_client(self.tool_config.get("connection_string"))
        log.info("Database tool initialized")
    
    async def cleanup(self, component: SamAgentComponent, tool_config: AnyToolConfig):
        """Cleanup on agent shutdown."""
        log.info("Cleaning up database tool...")
        if hasattr(self, "db_client"):
            await self.db_client.close()
        log.info("Database tool cleaned up")
    
    async def _run_async_impl(self, args: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Use initialized client."""
        if not hasattr(self, "db_client"):
            return {"error": "Database not initialized"}
        
        results = await self.db_client.execute(args["query"])
        return {"results": results}
```

---

## MCP (Model Context Protocol) Tools

### What is MCP?

MCP enables agents to use tools from external servers, allowing:

- **Language-Agnostic Tools**: Tools written in any language
- **Standalone Services**: Tools run in separate processes
- **Reusable Components**: Share tools across projects

### Configure MCP Tools

#### Step 1: Install MCP Server

```bash
# Install from npm
npm install -g @modelcontextprotocol/server-filesystem

# Or use existing MCP server
```

#### Step 2: Configure in Agent

```yaml
tools:
  - tool_type: mcp
    server_name: "filesystem"
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
      - "/path/to/allowed/directory"
    env:
      NODE_ENV: "production"
```

#### Step 3: Use MCP Tools

The agent automatically discovers and uses tools from the MCP server.

### Common MCP Servers

**Filesystem Server:**
```yaml
- tool_type: mcp
  server_name: "filesystem"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
```

**GitHub Server:**
```yaml
- tool_type: mcp
  server_name: "github"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-github"]
  env:
    GITHUB_TOKEN: ${GITHUB_TOKEN}
```

**Custom MCP Server:**
```yaml
- tool_type: mcp
  server_name: "my-custom-server"
  command: "python"
  args: ["-m", "my_mcp_server"]
  env:
    API_KEY: ${MY_API_KEY}
```

---

## Tool Configuration Patterns

### Pattern 1: Multiple Tool Configurations

**Use Case:** Same tool with different settings

```yaml
tools:
  # Production API
  - tool_type: python
    component_module: "my_agent.api_tools"
    function_name: "call_api"
    tool_name: "call_production_api"
    tool_description: "Call production API endpoint"
    tool_config:
      api_url: ${PROD_API_URL}
      api_key: ${PROD_API_KEY}
      timeout: 30
  
  # Staging API
  - tool_type: python
    component_module: "my_agent.api_tools"
    function_name: "call_api"
    tool_name: "call_staging_api"
    tool_description: "Call staging API endpoint"
    tool_config:
      api_url: ${STAGING_API_URL}
      api_key: ${STAGING_API_KEY}
      timeout: 60
```

---

### Pattern 2: Conditional Tool Loading

**Use Case:** Different tools for different environments

```yaml
tools:
  # Always include
  - tool_type: builtin-group
    group_name: "artifact_management"
  
  # Development only
  - tool_type: python
    component_module: "my_agent.debug_tools"
    function_name: "debug_state"
    tool_config:
      enabled: ${DEBUG_MODE, false}
  
  # Production only
  - tool_type: python
    component_module: "my_agent.monitoring_tools"
    function_name: "send_metrics"
    tool_config:
      enabled: ${PRODUCTION_MODE, false}
```

---

### Pattern 3: Tool Composition

**Use Case:** Build complex capabilities from simple tools

```yaml
tools:
  # Data fetching
  - tool_type: python
    component_module: "my_agent.data_tools"
    function_name: "fetch_data"
  
  # Data transformation
  - tool_type: python
    component_module: "my_agent.data_tools"
    function_name: "transform_data"
  
  # Data visualization
  - tool_type: builtin
    tool_name: "create_chart_from_plotly_config"
  
  # Artifact storage
  - tool_type: builtin-group
    group_name: "artifact_management"
```

The agent can chain these tools to: fetch → transform → visualize → save

---

## Complete Configuration Examples

### Example 1: Data Analysis Agent

```yaml
app_config:
  agent_name: "data-analyst"
  
  instruction: |
    You are a data analysis specialist.
    Use your tools to query, transform, and visualize data.
  
  tools:
    # Database access
    - tool_type: builtin-group
      group_name: "data_analysis"
      tool_config:
        sqlite_memory_threshold_mb: 200
        max_result_preview_rows: 100
    
    # File management
    - tool_type: builtin-group
      group_name: "artifact_management"
    
    # Custom data processing
    - tool_type: python
      component_module: "my_agent.data_tools"
      function_name: "advanced_statistics"
      component_base_path: "src"
```

---

### Example 2: API Integration Agent

```yaml
app_config:
  agent_name: "api-connector"
  
  tools:
    # Web requests
    - tool_type: builtin-group
      group_name: "web"
    
    # Custom API wrapper
    - tool_type: python
      component_module: "my_agent.api_tools"
      class_name: "ExternalAPITool"
      component_base_path: "src"
      init_function: "initialize_api_client"
      cleanup_function: "cleanup_api_client"
      tool_config:
        api_base_url: ${EXTERNAL_API_URL}
        api_key: ${EXTERNAL_API_KEY}
        rate_limit: 100
        timeout: 30
```

---

### Example 3: Multimodal Agent

```yaml
app_config:
  agent_name: "multimodal-agent"
  model: *multimodal_model
  
  tools:
    # Image tools
    - tool_type: builtin-group
      group_name: "image"
    
    # Audio tools
    - tool_type: builtin-group
      group_name: "audio"
    
    # File management
    - tool_type: builtin-group
      group_name: "artifact_management"
    
    # Document conversion
    - tool_type: builtin
      tool_name: "convert_file_to_markdown"
```

---

## Troubleshooting

### Issue: Tool not found

**Symptoms:**
```
Error: Tool 'my_tool' not found in registry
```

**Solutions:**

1. **Verify tool configuration:**
```yaml
tools:
  - tool_type: python
    component_module: "my_agent.tools"
    function_name: "my_tool"  # Must match function name
```

2. **Check file exists:**
```bash
ls src/my_agent/tools.py
```

3. **Test import:**
```bash
python -c "from my_agent.tools import my_tool"
```

4. **Add base_path:**
```yaml
component_base_path: "src"
```

---

### Issue: Tool execution fails

**Symptoms:**
```
Error executing tool: ModuleNotFoundError
```

**Solutions:**

1. **Check PYTHONPATH:**
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Verify tool signature:**
```python
# Must be async
async def my_tool(param: str, tool_context=None, tool_config=None):
    pass
```

---

### Issue: Tool config not passed

**Symptoms:**
- Tool receives None for tool_config
- Configuration values not available

**Solutions:**

1. **Verify YAML structure:**
```yaml
tools:
  - tool_type: python
    component_module: "my_agent.tools"
    function_name: "my_tool"
    tool_config:  # Must be at this level
      api_key: ${API_KEY}
```

2. **Check environment variables:**
```bash
echo $API_KEY
```

3. **Use defaults in tool:**
```python
api_key = tool_config.get("api_key", "default") if tool_config else "default"
```

---

## Best Practices

### Tool Design

1. **Single Purpose**: Each tool should do one thing well
2. **Clear Docstrings**: LLM uses these to understand when to use the tool
3. **Type Hints**: Provide clear parameter types
4. **Error Handling**: Return structured errors, don't raise exceptions
5. **Async Operations**: Always use async/await

### Configuration

1. **Use Environment Variables**: For sensitive data
2. **Provide Defaults**: Make tools work out of the box when possible
3. **Validate Inputs**: Check parameters before processing
4. **Document Config**: Explain what each config option does

### Performance

1. **Cache Results**: Store frequently accessed data
2. **Batch Operations**: Process multiple items together
3. **Async I/O**: Use async for network/file operations
4. **Limit Output**: Don't return massive datasets

### Security

1. **Validate Inputs**: Sanitize user-provided data
2. **Secure Credentials**: Never log API keys or passwords
3. **Rate Limiting**: Implement rate limits for external APIs
4. **Audit Logging**: Log tool usage for security monitoring

---

## Validation Checklist

Before deploying tools:

- [ ] Tool functions are async
- [ ] Docstrings are clear and complete
- [ ] Type hints are provided
- [ ] Error handling is implemented
- [ ] Configuration is validated
- [ ] Environment variables are set
- [ ] Dependencies are installed
- [ ] Tools are tested individually
- [ ] Lifecycle functions work correctly
- [ ] Security considerations addressed

---

## Next Steps

After configuring tools:

1. **Test Tools**: Verify each tool works correctly
2. **Monitor Usage**: Track which tools are used most
3. **Optimize Performance**: Improve slow tools
4. **Add More Tools**: Expand agent capabilities
5. **Create Plugins**: Package tools for reuse

---

## Additional Resources

- [Built-in Tools Reference](https://docs.cline.bot/components/builtin-tools/builtin-tools)
- [Creating Python Tools Guide](https://docs.cline.bot/developing/creating-python-tools)
- [MCP Integration Tutorial](https://docs.cline.bot/developing/tutorials/mcp-integration)
- [Tool Development Best Practices](https://docs.cline.bot/developing/developing)