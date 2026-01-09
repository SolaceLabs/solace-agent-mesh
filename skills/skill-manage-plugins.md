# Skill: Manage Plugins in Solace Agent Mesh

## Skill ID
`manage-plugins`

## Description
Create, build, install, and manage plugins in Solace Agent Mesh. Plugins provide modular, reusable components (agents, gateways, tools) that can be shared across projects and teams.

## Prerequisites
- Initialized Agent Mesh project (see `skill-initialize-project`)
- Python development environment
- Understanding of Python packaging
- Git (for sharing plugins)

## Related Skills
- `create-and-manage-agents` - Agent development
- `create-and-manage-gateways` - Gateway development
- `configure-agent-tools` - Tool development

---

## Core Concepts

### What are Plugins?

Plugins are packaged Python modules that extend Agent Mesh with:

1. **Agent Plugins**: Pre-configured specialized agents
2. **Gateway Plugins**: Custom interface implementations
3. **Custom Plugins**: Specialized integrations (HR providers, etc.)

### Plugin vs Standalone Component

| Aspect | Standalone Component | Plugin |
|--------|---------------------|--------|
| **Scope** | Single project | Multiple projects |
| **Distribution** | Copy files | Python package |
| **Versioning** | Project version | Independent version |
| **Reusability** | Low | High |
| **Maintenance** | Per-project | Centralized |

### Plugin Architecture

```
Plugin Package (.whl)
├── Configuration Template
├── Python Code (tools, logic)
├── Dependencies
└── Documentation

Installation
├── pip install plugin.whl
└── sam plugin add instance-name --plugin plugin-name

Result
└── configs/agents/instance-name.yaml (or gateways/)
```

---

## Plugin Lifecycle

### 1. Create Plugin

```bash
sam plugin create my-plugin --type agent
```

### 2. Develop Plugin

Edit code and configuration in plugin directory

### 3. Build Plugin

```bash
cd my-plugin
sam plugin build
```

Creates: `dist/my_plugin-0.1.0-py3-none-any.whl`

### 4. Install Plugin

```bash
sam plugin install ./dist/my_plugin-0.1.0-py3-none-any.whl
```

### 5. Use Plugin

```bash
sam plugin add my-instance --plugin my-plugin
```

---

## Step-by-Step Instructions

### Create Agent Plugin

#### Step 1: Initialize Plugin

```bash
sam plugin create weather-agent --type agent
```

**Interactive Prompts:**
```
? Author name: John Doe
? Author email: john@example.com
? Description: Weather data analysis agent
? Version: 0.1.0
```

**Created Structure:**
```
weather-agent/
├── src/
│   └── weather_agent/
│       ├── __init__.py
│       ├── tools.py
│       └── lifecycle.py
├── config.yaml
├── pyproject.toml
├── README.md
└── .gitignore
```

#### Step 2: Develop Tools

Edit `src/weather_agent/tools.py`:

```python
from typing import Any, Dict, Optional
from google.adk.tools import ToolContext
from solace_ai_connector.common.log import log

async def get_weather(
    city: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get current weather for a city.
    
    Args:
        city: City name
    
    Returns:
        Weather information
    """
    api_key = tool_config.get("api_key") if tool_config else None
    
    # Implementation
    log.info(f"Fetching weather for {city}")
    
    return {
        "city": city,
        "temperature": 72,
        "conditions": "sunny"
    }
```

#### Step 3: Configure Plugin

Edit `config.yaml`:

```yaml
apps:
  - name: weather-agent
    app_module: solace_agent_mesh.agent.sac.app
    
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: ${NAMESPACE}
      agent_name: "weather-agent"
      
      model: *general_model
      
      instruction: |
        You are a weather information specialist.
        Provide accurate weather data and forecasts.
      
      tools:
        - tool_type: python
          component_module: "weather_agent.tools"
          function_name: "get_weather"
          tool_config:
            api_key: ${WEATHER_API_KEY}
      
      agent_card:
        description: "Weather data and forecast specialist"
        skills:
          - id: "get_weather"
            name: "Get Weather"
            description: "Get current weather for any city"
      
      session_service: *default_session_service
      artifact_service: *default_artifact_service
```

#### Step 4: Build Plugin

```bash
cd weather-agent
sam plugin build
```

**Output:**
```
Building plugin...
Successfully built weather_agent-0.1.0-py3-none-any.whl
Wheel saved to: dist/weather_agent-0.1.0-py3-none-any.whl
```

#### Step 5: Install and Use

```bash
# Install plugin
sam plugin install ./dist/weather_agent-0.1.0-py3-none-any.whl

# Create instance
sam plugin add my-weather-agent --plugin weather-agent

# Run
sam run configs/agents/my_weather_agent.yaml
```

---

### Create Gateway Plugin

#### Step 1: Initialize

```bash
sam plugin create custom-gateway --type gateway
```

#### Step 2: Implement Gateway

Edit `src/custom_gateway/gateway.py`:

```python
from solace_agent_mesh.gateway.base_gateway import BaseGateway

class CustomGateway(BaseGateway):
    """Custom gateway implementation."""
    
    async def initialize(self):
        """Initialize gateway."""
        await super().initialize()
        # Custom initialization
    
    async def handle_request(self, request):
        """Handle incoming request."""
        # Transform request to stimulus
        stimulus = self.create_stimulus(request)
        
        # Send to agent mesh
        response = await self.send_stimulus(stimulus)
        
        # Transform response
        return self.format_response(response)
```

#### Step 3: Configure

Edit `config.yaml` with gateway-specific settings.

#### Step 4: Build and Use

Same as agent plugin.

---

### Create Custom Plugin

#### Step 1: Initialize

```bash
sam plugin create hr-integration --type custom
```

#### Step 2: Implement Custom Logic

```python
# src/hr_integration/provider.py
class HRProvider:
    """HR system integration."""
    
    async def get_employee_info(self, employee_id):
        """Fetch employee information."""
        # Implementation
        pass
```

#### Step 3: Build and Use

Same process as other plugin types.

---

## Using Existing Plugins

### Install from PyPI

```bash
sam plugin install package-name
```

### Install from Git

```bash
sam plugin install git+https://github.com/user/repo.git
```

### Install from Local Path

```bash
sam plugin install /path/to/plugin
```

### Install from Wheel

```bash
sam plugin install /path/to/plugin.whl
```

---

## Plugin Catalog

### Launch Catalog Dashboard

```bash
sam plugin catalog
```

**Features:**
- Browse available plugins
- View plugin details
- Install plugins with one click
- Manage installed plugins

**Access:** `http://localhost:5003`

---

## Official Core Plugins

### Available Plugins

1. **sam-event-mesh-gateway**: External event mesh connectivity
2. **sam-slack-gateway**: Slack bot integration
3. **sam-teams-gateway**: Microsoft Teams integration (Enterprise)
4. **sam-markitdown-agent**: Document conversion agent
5. **sam-mermaid-agent**: Diagram generation agent
6. **sam-web-agent**: Web scraping and interaction

### Install Core Plugin

```bash
# Install by name (from official repository)
sam plugin install sam-slack-gateway

# Add instance
sam plugin add my-slack-bot --plugin sam-slack-gateway
```

---

## Plugin Configuration

### pyproject.toml

```toml
[project]
name = "my-plugin"
version = "0.1.0"
description = "My custom Agent Mesh plugin"
authors = [{name = "Your Name", email = "you@example.com"}]
requires-python = ">=3.10"
dependencies = [
    "solace-agent-mesh>=0.3.0",
    "requests>=2.31.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=23.0.0",
]

[build-system]
requires = ["setuptools>=68.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

### README.md Template

```markdown
# My Plugin

Description of what the plugin does.

## Installation

\`\`\`bash
sam plugin install my-plugin
\`\`\`

## Usage

\`\`\`bash
sam plugin add my-instance --plugin my-plugin
\`\`\`

## Configuration

Required environment variables:
- `API_KEY`: Your API key
- `ENDPOINT`: API endpoint URL

## Features

- Feature 1
- Feature 2

## License

MIT
```

---

## Advanced Plugin Patterns

### Pattern 1: Configurable Plugin

**Use Case:** Plugin with multiple configuration options

```yaml
# config.yaml
apps:
  - name: configurable-agent
    app_config:
      # Expose configuration options
      api_endpoint: ${API_ENDPOINT}
      api_key: ${API_KEY}
      timeout: ${TIMEOUT, 30}
      retry_count: ${RETRY_COUNT, 3}
```

**Usage:**
```bash
# User sets environment variables
export API_ENDPOINT=https://api.example.com
export API_KEY=secret-key

sam plugin add my-instance --plugin configurable-agent
```

---

### Pattern 2: Multi-Tool Plugin

**Use Case:** Plugin providing multiple related tools

```python
# src/my_plugin/tools.py

async def tool_1(param: str, **kwargs):
    """First tool."""
    pass

async def tool_2(param: str, **kwargs):
    """Second tool."""
    pass

async def tool_3(param: str, **kwargs):
    """Third tool."""
    pass
```

```yaml
# config.yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "tool_1"
  
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "tool_2"
  
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "tool_3"
```

---

### Pattern 3: Plugin with Dependencies

**Use Case:** Plugin requiring external packages

```toml
# pyproject.toml
dependencies = [
    "solace-agent-mesh>=0.3.0",
    "requests>=2.31.0",
    "pandas>=2.0.0",
    "sqlalchemy>=2.0.0",
]
```

Dependencies are automatically installed with the plugin.

---

## Sharing Plugins

### Publish to PyPI

```bash
# Build
sam plugin build

# Upload to PyPI
pip install twine
twine upload dist/*
```

### Share via Git

```bash
# Initialize git
git init
git add .
git commit -m "Initial commit"

# Push to GitHub
git remote add origin https://github.com/user/my-plugin.git
git push -u origin main
```

**Install from Git:**
```bash
sam plugin install git+https://github.com/user/my-plugin.git
```

### Share Wheel File

```bash
# Build wheel
sam plugin build

# Share dist/my_plugin-0.1.0-py3-none-any.whl
# Users install with:
sam plugin install /path/to/my_plugin-0.1.0-py3-none-any.whl
```

---

## Plugin Management Commands

### List Installed Plugins

```bash
sam plugin list
```

### Update Plugin

```bash
# Rebuild
cd my-plugin
sam plugin build

# Reinstall
sam plugin install ./dist/my_plugin-0.2.0-py3-none-any.whl --upgrade
```

### Remove Plugin

```bash
pip uninstall my-plugin
```

### Custom Install Command

```bash
# Use uv instead of pip
export SAM_PLUGIN_INSTALL_COMMAND="uv pip install {package}"

# Or pass as option
sam plugin install my-plugin --install-command "uv pip install {package}"
```

---

## Troubleshooting

### Issue: Plugin build fails

**Symptoms:**
```
Error: Failed to build plugin
```

**Solutions:**

1. **Check pyproject.toml:**
```bash
cat pyproject.toml
```

2. **Install build dependencies:**
```bash
pip install build setuptools wheel
```

3. **Verify Python version:**
```bash
python --version  # Should be 3.10+
```

---

### Issue: Plugin not found after install

**Symptoms:**
```
Error: Plugin 'my-plugin' not found
```

**Solutions:**

1. **Verify installation:**
```bash
pip list | grep my-plugin
```

2. **Check plugin name:**
```bash
# Use exact package name
sam plugin add instance --plugin my_plugin  # Note underscore
```

3. **Reinstall:**
```bash
pip uninstall my-plugin
sam plugin install ./dist/my_plugin-0.1.0-py3-none-any.whl
```

---

### Issue: Import errors when using plugin

**Symptoms:**
```
ModuleNotFoundError: No module named 'my_plugin'
```

**Solutions:**

1. **Check package structure:**
```bash
# Verify src/my_plugin/__init__.py exists
ls src/my_plugin/__init__.py
```

2. **Verify pyproject.toml:**
```toml
[tool.setuptools.packages.find]
where = ["src"]
```

3. **Rebuild and reinstall:**
```bash
sam plugin build
sam plugin install ./dist/my_plugin-0.1.0-py3-none-any.whl --force-reinstall
```

---

## Best Practices

### Development

1. **Version Control**: Use git from the start
2. **Semantic Versioning**: Follow semver (0.1.0, 0.2.0, 1.0.0)
3. **Documentation**: Write clear README and docstrings
4. **Testing**: Include unit tests
5. **Dependencies**: Pin major versions, allow minor updates

### Configuration

1. **Environment Variables**: Use for sensitive data
2. **Defaults**: Provide sensible defaults
3. **Validation**: Validate configuration on startup
4. **Documentation**: Document all config options

### Distribution

1. **README**: Include installation and usage instructions
2. **Examples**: Provide example configurations
3. **Changelog**: Document changes between versions
4. **License**: Include appropriate license file

### Maintenance

1. **Compatibility**: Test with different Agent Mesh versions
2. **Updates**: Keep dependencies updated
3. **Issues**: Respond to user issues promptly
4. **Deprecation**: Provide migration guides for breaking changes

---

## Validation Checklist

Before publishing a plugin:

- [ ] Plugin builds successfully
- [ ] All dependencies are listed
- [ ] README is complete and clear
- [ ] Examples are provided
- [ ] Tests pass
- [ ] Version number is correct
- [ ] License is included
- [ ] Plugin installs correctly
- [ ] Plugin works in fresh project
- [ ] Documentation is accurate

---

## Next Steps

After creating plugins:

1. **Test Thoroughly**: Test in multiple projects
2. **Document**: Write comprehensive documentation
3. **Share**: Publish to PyPI or GitHub
4. **Maintain**: Respond to issues and update regularly
5. **Promote**: Share with community

---

## Additional Resources

- [Plugin Documentation](https://docs.cline.bot/components/plugins)
- [Official Core Plugins](https://github.com/SolaceLabs/solace-agent-mesh-core-plugins)
- [Python Packaging Guide](https://packaging.python.org/)
- [Semantic Versioning](https://semver.org/)