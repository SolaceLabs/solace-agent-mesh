# Solace Agent Mesh Development Guide

**Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Working Effectively

### Bootstrap and Setup
- **Install Python 3.10.16+ and hatch**:
  ```bash
  python3 -m pip install hatch
  ```
- **Create development environment**: 
  ```bash
  hatch env create
  ```
  - **TIMING**: 10-15 minutes on first run. NEVER CANCEL. Set timeout to 30+ minutes.
  - **NOTE**: May fail due to network timeouts - if this happens, the project can still be worked on using direct pip installs for specific dependencies.

### Alternative Setup (if hatch fails)
- **Install basic dependencies manually**:
  ```bash
  pip install --user flask flask_cors click rich pydantic PyYAML pytest
  ```
- **Set Python path when running CLI**:
  ```bash
  export PYTHONPATH=cli:src:tests/sam-test-infrastructure/src
  ```

### Frontend Development Setup
- **Install Node.js dependencies**:
  ```bash
  cd client/webui/frontend
  npm ci
  ```
  - **TIMING**: ~15 seconds. Set timeout to 2+ minutes.
- **Build frontend**:
  ```bash
  npm run build
  ```
  - **TIMING**: ~10 seconds. Set timeout to 2+ minutes.
- **Build frontend as reusable library**:
  ```bash
  npm run build-package  
  ```
  - **TIMING**: ~8 seconds. Set timeout to 2+ minutes.

### Testing
- **Frontend linting**:
  ```bash
  cd client/webui/frontend
  npm run lint
  ```
  - **TIMING**: ~5 seconds. Set timeout to 1+ minute.
- **Python unit tests**:
  ```bash
  PYTHONPATH=cli:src:tests/sam-test-infrastructure/src python3 -m pytest tests/unit -v
  ```
  - **NOTE**: Requires pytest-asyncio and many dependencies. Use hatch environment when possible.
- **Integration tests**:
  ```bash
  hatch run test
  ```
  - **TIMING**: Long-running tests exist (stress tests can take hours). NEVER CANCEL. Set timeout to 180+ minutes for full test suite.

### Running the Application
- **CLI tool** (when dependencies available):
  ```bash
  # With hatch environment
  hatch shell
  sam --help
  
  # Or directly (requires PYTHONPATH)
  PYTHONPATH=cli:src python3 cli/main.py --help
  ```
- **Initialize new project**:
  ```bash
  sam init --gui  # Runs on port 5002
  ```
- **Run project**:
  ```bash
  sam run  # Web UI available at http://localhost:8000
  ```
- **Add agent with GUI**:
  ```bash
  sam add agent --gui
  ```

## Validation

### Always Validate Changes
- **Run frontend linting before commits**:
  ```bash
  cd client/webui/frontend && npm run lint
  ```
- **Run pre-commit hooks**: The `.hooks/pre-commit` script runs `npm run precommit` for frontend changes
- **Test CLI functionality**: Always test `sam --help` and basic commands after making CLI changes
- **Frontend development server**: Use `npm run dev` in `client/webui/frontend/` for UI changes

### Manual Testing Scenarios
- **CLI Workflow**: Test `sam init --skip`, create agent configs, validate YAML generation
- **Frontend Build**: Ensure both `npm run build` and `npm run build-package` work without errors
- **Integration**: When possible, test that the frontend can communicate with backend services

## Architecture Overview

The Solace Agent Mesh is a distributed AI agent communication system built on the Solace event mesh. It enables real-time Agent-to-Agent (A2A) communication, task delegation, and multi-platform integration through event-driven architecture principles.

### Architectural Principles

Built on three primary technologies:
- **Solace PubSub+ Event Broker**: Messaging fabric for all asynchronous communication using topic-based routing for A2A protocol
- **Solace AI Connector (SAC)**: Runtime environment for hosting and managing lifecycle of all system components (Agents and Gateways)  
- **Google Agent Development Kit (ADK)**: Core logic for individual agents, including LLM interaction, tool execution, and state management

Key architectural principles:
- **Event-Driven Architecture (EDA)**: All interactions are asynchronous and mediated by the event broker
- **Component Decoupling**: Gateways, Agent Hosts communicate through standardized A2A protocol messages
- **Scalability and Resilience**: Supports horizontal scaling with fault tolerance and guaranteed message delivery

### Core System Components

#### 1. Solace PubSub+ Event Broker
**Purpose**: Central messaging fabric routing A2A protocol messages between components using hierarchical topic structure.

**A2A Protocol Topics**:
- **Agent Discovery**: `{namespace}/a2a/v1/discovery/agentcards`
- **Task Requests**: `{namespace}/a2a/v1/agent/request/{target_agent_name}`
- **Status Updates**: `{namespace}/a2a/v1/gateway/status/{gateway_id}/{task_id}`
- **Final Responses**: `{namespace}/a2a/v1/gateway/response/{gateway_id}/{task_id}`
- **Peer Delegation**: `{namespace}/a2a/v1/agent/status|response/{delegating_agent_name}/{sub_task_id}`

#### 2. Agent Framework (`src/solace_agent_mesh/agent/`)
**Purpose**: Complete framework for hosting Google ADK (Agent Development Kit) agents with A2A protocol support and comprehensive tool library.

**Key Subsystems**:
- **`sac/`** (Solace AI Connector): Main entry point with `SamAgentApp` and `SamAgentComponent` for hosting agents
- **`adk/`** (Agent Development Kit): Core integration layer with Google's ADK, custom `AppLlmAgent`, and rich callbacks
- **`tools/`**: Comprehensive tool library for data analysis, web requests, multimedia processing, inter-agent communication
- **`protocol/`**: A2A communication protocol implementation for message routing
- **`utils/`**: Helper utilities for configuration, context handling, artifact management

**Key Imports**:
```python
from solace_agent_mesh.agent.sac.app import SamAgentApp
from solace_agent_mesh.agent.sac.component import SamAgentComponent
from solace_agent_mesh.agent.adk.app_llm_agent import AppLlmAgent
from solace_agent_mesh.agent.tools.peer_agent_tool import PeerAgentTool
from solace_agent_mesh.agent.tools.builtin_data_analysis_tools import query_data_with_sql
from solace_agent_mesh.agent.tools.web_tools import web_request
from solace_agent_mesh.agent.tools.image_tools import create_image_from_description
```

#### 2. Common Infrastructure (`src/solace_agent_mesh/common/`)
**Purpose**: Foundational A2A protocol infrastructure, type systems, and client/server implementations.

**Key Exports**: A2A protocol functions, Pydantic types (`Message`, `Task`, `AgentCard`), `A2AClient`, `A2AServer`, utilities

**Key Imports**:
```python
from solace_agent_mesh.common.a2a_protocol import get_agent_request_topic
from solace_agent_mesh.common.types import Message, Task, AgentCard, TextPart
from solace_agent_mesh.common.client import A2AClient, A2ACardResolver
from solace_agent_mesh.common.server import A2AServer, InMemoryTaskManager
from solace_agent_mesh.common.agent_registry import AgentRegistry
from solace_agent_mesh.common.utils.embeds import resolve_embeds_recursively_in_string
```

#### 3. Core A2A Service (`src/solace_agent_mesh/core_a2a/`)
**Purpose**: Reusable service layer for core A2A interactions, task submission, cancellation, and agent discovery.

**Key Imports**:
```python
from solace_agent_mesh.core_a2a.service import CoreA2AService
```

#### 5. Orchestrator Agent
**Purpose**: Specialized agent that provides centralized workflow management and task coordination in the distributed system.

**Key Functions**:
- **Request Analysis**: Receives high-level goals and analyzes them in context of available agent capabilities
- **Action Planning**: Uses AI to plan sequences of actions to fulfill complex requests
- **Task Distribution**: Creates and distributes tasks to appropriate agents with parallel processing
- **Workflow Management**: Tracks outstanding tasks and aggregates responses coherently
- **Response Formatting**: Formats aggregated responses suitable for gateways

**Configuration**: Typically configured as `main_orchestrator.yaml` in `configs/agents/` directory.

#### 4. Gateway Framework (`src/solace_agent_mesh/gateway/`)
**Purpose**: Framework for building gateways that bridge external platforms with the A2A messaging system.

**Available Gateways**:
- **HTTP/SSE Gateway**: Web UI backend with FastAPI, real-time streaming via Server-Sent Events
- **Slack Gateway**: Integration with Slack for team collaboration
- **Webhook Gateway**: HTTP webhook integration for external systems

**Key Imports**:
```python
from solace_agent_mesh.gateway.base.app import BaseGatewayApp
from solace_agent_mesh.gateway.http_sse.app import WebUIBackendApp
from solace_agent_mesh.gateway.slack.app import SlackGatewayApp
from solace_agent_mesh.gateway.webhook.app import WebhookGatewayApp
```

## Project Structure and Configuration

### Standard Project Organization
```
my-sam-project/
├── configs/
│   ├── shared_config.yaml           # Shared broker, models, and services config
│   ├── agents/
│   │   └── main_orchestrator.yaml   # Default orchestrator agent
│   └── gateways/
│       └── webui.yaml              # Default web UI gateway
│   ├── plugins/                    # Plugin configurations (auto-created)
├── src/                            # Custom Python components (optional)
│   └── __init__.py
├── .env                           # Environment variables
└── requirements.txt               # Custom dependencies
```

### Configuration Management Patterns
- **Shared Configuration**: `shared_config.yaml` contains common elements (broker, models, services) referenced via YAML anchors (`&name` and `*name`)
- **Environment Variables**: Configuration values use env vars for flexibility across environments  
- **Automatic Generation**: `sam add agent`, `sam add gateway`, `sam plugin add` generate appropriate config files
- **File Discovery**: CLI crawls configs directory, ignores files starting with `_` or `shared_config`
- **Standalone Execution**: Each config file can run independently with `sam run <config-file>`

### YAML Configuration Structure
Each configuration file defines applications that can run independently:
- **Agent Applications**: A2A-enabled agents using Google ADK runtime and SAM framework
- **Gateway Applications**: Protocol translators bridging external interfaces to A2A protocol  
- **Plugin Applications**: Specialized components extending framework capabilities

## Built-in Tool Groups and Configuration

SAM provides comprehensive built-in tools organized into logical groups for easy configuration:

**Tool Groups** (recommended approach for enabling related tools):
```yaml
tools:
  - tool_type: builtin-group
    group_name: "artifact_management"
  - tool_type: builtin-group  
    group_name: "data_analysis"
  - tool_type: builtin-group
    group_name: "web"
  - tool_type: builtin-group
    group_name: "audio"
  - tool_type: builtin-group
    group_name: "communication"
```

**Available Tool Groups**:
- **`artifact_management`**: create_artifact, append_to_artifact, list_artifacts, load_artifact, signal_artifact_for_return, extract_content_from_artifact
- **`data_analysis`**: query_data_with_sql, create_sqlite_db, transform_data_with_jq, create_chart_from_plotly_config
- **`web`**: web_request, web_scraping tools
- **`audio`**: text_to_speech, multi_speaker_text_to_speech, audio processing tools
- **`communication`**: peer_agent_tool for inter-agent delegation

**Individual Tool Configuration**:
```yaml
tools:
  - tool_type: builtin
    tool_name: "peer_agent_tool"
  - tool_type: builtin
    tool_name: "web_request"
    tool_config:
      timeout: 30
      max_retries: 3
```

## Development Patterns & Usage

### 1. Creating ADK Agents

**Agent Configuration (YAML)**:
```yaml
app:
  class_name: solace_agent_mesh.agent.sac.app.SamAgentApp
  app_config:
    namespace: "myorg/ai-agents"
    agent_name: "data_analyst"
    model: "gemini-1.5-pro"
    instruction: "You are a data analysis expert with access to comprehensive tools."
    tools:
      - tool_type: "builtin"
        tool_name: "query_data_with_sql"
      - tool_type: "builtin" 
        tool_name: "create_chart"
      - tool_type: "builtin"
        tool_name: "peer_agent_tool"
    agent_card:
      description: "AI agent for data analysis and reporting"
      capabilities: ["data_analysis", "chart_generation", "peer_collaboration"]
    session_service:
      type: "memory"
    artifact_service:
      type: "filesystem"
      base_path: "/tmp/artifacts"
```

**Programmatic Agent Setup**:
```python
from solace_agent_mesh.agent.adk.setup import load_adk_tools, initialize_adk_agent, initialize_adk_runner
from solace_agent_mesh.agent.adk.services import initialize_session_service, initialize_artifact_service

async def setup_agent(component):
    # Initialize services
    session_service = initialize_session_service(component)
    artifact_service = initialize_artifact_service(component)
    
    # Load tools (Python functions, MCP tools, built-ins)
    loaded_tools, builtin_tools = await load_adk_tools(component)
    
    # Initialize agent with rich callbacks
    agent = initialize_adk_agent(component, loaded_tools, builtin_tools)
    
    # Initialize async task runner
    runner = initialize_adk_runner(component)
    
    return agent, runner
```

### 2. Building Custom Tools

**Tool Development Pattern**:
```python
from solace_agent_mesh.agent.tools.registry import tool_registry
from solace_agent_mesh.agent.tools.tool_definition import BuiltinTool
from google.adk.tools import ToolContext

async def custom_data_processor(
    query: str,
    database: str = "default",
    tool_context: ToolContext = None,
    tool_config: dict = None
) -> dict:
    """Process data with enhanced features and artifact management."""
    
    # Access host component for shared resources
    host_component = tool_context._invocation_context.agent.host_component
    
    # Get shared services
    db_connection = host_component.get_agent_specific_state('db_connection')
    artifact_service = host_component.get_shared_artifact_service()
    
    try:
        # Process data
        result = await process_data(db_connection, query, database)
        
        # Save results as artifact with metadata
        from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata
        import json
        from datetime import datetime, timezone
        
        artifact_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=host_component.get_config()["app_name"],
            user_id=tool_context.user_id,
            session_id=tool_context.session_id,
            filename=f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            content_bytes=json.dumps(result).encode(),
            mime_type="application/json",
            metadata_dict={
                "query": query,
                "database": database,
                "tool": "custom_data_processor"
            },
            timestamp=datetime.now(timezone.utc)
        )
        
        return {
            "status": "success",
            "rows_processed": len(result),
            "artifact_filename": artifact_result["filename"]
        }
        
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Register the tool
tool_registry.register(BuiltinTool(
    name="custom_data_processor",
    description="Process data with enhanced features",
    function=custom_data_processor,
    category="data_analysis"
))
```

### 3. Inter-Agent Communication

**Peer Agent Tool Usage**:
```python
from solace_agent_mesh.agent.tools.peer_agent_tool import PeerAgentTool

async def delegate_to_specialist(component, tool_context):
    # Create peer agent tool
    peer_tool = PeerAgentTool("report_generator", component)
    
    # Delegate task with artifact reference
    result = await peer_tool.run_async(
        args={
            "task_description": "Generate PDF report from analysis",
            "analysis_data": "artifact://analysis_result.json",
            "report_format": "PDF"
        },
        tool_context=tool_context
    )
    
    return result
```

### 4. Gateway Development

**HTTP/SSE Gateway Setup**:
```python
from solace_agent_mesh.gateway.http_sse.app import WebUIBackendApp

webui_config = {
    "name": "web-gateway",
    "app_config": {
        "namespace": "myorg/ai-agents",
        "gateway_id": "web-ui-gateway", 
        "session_secret_key": "secret-key",
        "fastapi_host": "0.0.0.0",
        "fastapi_port": 8080,
        "cors_allowed_origins": ["http://localhost:3000"],
        "artifact_service": {"type": "local_file", "base_path": "./artifacts"}
    }
}

webui_app = WebUIBackendApp(webui_config)
```

**Custom FastAPI Router with Dependencies**:
```python
from fastapi import APIRouter, Depends
from solace_agent_mesh.gateway.http_sse.dependencies import (
    get_agent_registry, get_user_id, get_publish_a2a_func
)

router = APIRouter()

@router.get("/custom-endpoint")
async def custom_endpoint(
    user_id: str = Depends(get_user_id),
    agent_registry = Depends(get_agent_registry),
    publish_func = Depends(get_publish_a2a_func)
):
    # Access discovered agents
    agents = agent_registry.get_all_agents()
    
    # Publish A2A message
    publish_func(
        topic=f"/namespace/a2a/v1/agent/request/target-agent",
        payload={"method": "custom/request", "params": {"user": user_id}},
        user_properties={"clientId": user_id}
    )
    
    return {"agents_count": len(agents)}
```

### 5. Multimedia Processing

**Audio and Image Tools**:
```python
from solace_agent_mesh.agent.tools.audio_tools import text_to_speech, multi_speaker_text_to_speech
from solace_agent_mesh.agent.tools.image_tools import create_image_from_description

async def multimedia_workflow(tool_context):
    # Generate speech
    tts_result = await text_to_speech(
        text="Welcome to the AI presentation system!",
        output_filename="intro.mp3",
        gender="female",
        tone="professional",
        tool_context=tool_context
    )
    
    # Multi-speaker dialogue
    conversation_result = await multi_speaker_text_to_speech(
        conversation_text="""
        Presenter: Today we'll discuss our results.
        Analyst: The data shows significant growth.
        """,
        speaker_configs=[
            {"name": "Presenter", "gender": "female", "tone": "professional"},
            {"name": "Analyst", "gender": "male", "tone": "analytical"}
        ],
        tool_context=tool_context
    )
    
    # Generate supporting visuals
    image_result = await create_image_from_description(
        image_description="Professional bar chart showing growth trends",
        output_filename="chart.png",
        tool_context=tool_context
    )
    
    return {"audio": tts_result, "dialogue": conversation_result, "chart": image_result}
```

### 6. Artifact Management

**Artifact Operations**:
```python
from solace_agent_mesh.agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    load_artifact_content_or_metadata,
    get_artifact_info_list
)

async def artifact_operations(component, artifact_service, tool_context):
    # Save artifact with metadata
    result = await save_artifact_with_metadata(
        artifact_service=artifact_service,
        app_name=component.get_config()["app_name"],
        user_id=tool_context.user_id,
        session_id=tool_context.session_id,
        filename="report.pdf",
        content_bytes=pdf_content,
        mime_type="application/pdf",
        metadata_dict={"type": "report", "generated_by": "ai_agent"},
        timestamp=datetime.now(timezone.utc)
    )
    
    # Load artifact
    loaded = await load_artifact_content_or_metadata(
        artifact_service=artifact_service,
        app_name=component.get_config()["app_name"],
        user_id=tool_context.user_id,
        session_id=tool_context.session_id,
        filename="report.pdf",
        version="latest"
    )
    
    return {"saved": result, "loaded": loaded}
```

### 7. Client-Side Integration

**A2A Client Usage**:
```python
import asyncio
from solace_agent_mesh.common.client import A2AClient, A2ACardResolver

async def client_integration():
    # Discover agents
    resolver = A2ACardResolver("https://agents.myorg.com")
    agent_card = resolver.get_agent_card()
    
    # Create client
    client = A2AClient(agent_card=agent_card)
    
    # Stream task with file upload
    task_payload = {
        "message": {
            "role": "user",
            "parts": [
                {"type": "text", "text": "Analyze this data"},
                {"type": "file", "file": {"name": "data.csv", "uri": "file://./data.csv"}}
            ]
        }
    }
    
    async for response in client.send_task_streaming(task_payload):
        if hasattr(response.result, 'text_delta'):
            print(response.result.text_delta, end='', flush=True)
        elif hasattr(response.result, 'artifact'):
            print(f"Artifact: {response.result.artifact.name}")
```

## Key Architecture Components

### Core Framework (Python)
- **Main package**: `src/solace_agent_mesh/` - Core framework code
- **CLI**: `cli/` - Command-line interface and utilities  
- **Configuration**: Uses YAML configs in `configs/` directories generated by CLI
- **Build system**: hatch (pyproject.toml) with custom build hooks for frontend assets

### Frontend (React TypeScript)
- **Location**: `client/webui/frontend/`
- **Build system**: Vite + TypeScript
- **Package**: Can be built as both standalone app and reusable library
- **Key scripts**: `dev`, `build`, `build-package`, `lint`, `precommit`

### Testing Infrastructure
- **Unit tests**: `tests/unit/` - Focus on CLI and core functionality
- **Integration tests**: `tests/integration/` - Full system testing with test infrastructure
- **Test infrastructure**: `tests/sam-test-infrastructure/` - Shared testing utilities
- **Long-running tests**: Marked with `@pytest.mark.long_soak` - can take hours

### Documentation and Examples
- **Documentation**: `docs/` - Built documentation system
- **Examples**: `examples/` - Sample configurations and use cases
- **Templates**: `templates/` - Code generation templates used by CLI

## Common Development Patterns

### File Organization
- **Agent configs**: Generated in `configs/agents/*.yaml` 
- **Component configs**: Generated in `configs/components/*.yaml`
- **Templates**: Located in `templates/` for code generation
- **Static assets**: Frontend builds output to `client/webui/frontend/static/`

### CLI Development
- **Commands**: Organized in `cli/commands/` by functionality
- **Utils**: Shared utilities in `cli/utils.py`
- **Testing**: Unit tests in `tests/unit/cli/` test configuration generation

### Frontend Development  
- **Components**: React components in `src/` with TypeScript
- **Styling**: Tailwind CSS with custom configuration
- **Build outputs**: Dual builds - full app and library package
- **Library exports**: Configured in `vite.lib.config.ts` for reusable components

## Important Constraints

### Network Dependencies
- **PyPI timeouts**: Network connectivity to PyPI may be limited - document when pip installs fail
- **NPM registry**: Frontend dependencies install reliably
- **Hatch environment**: May fail on first setup due to network issues

### Build Time Expectations
- **Frontend builds**: Fast (~10 seconds) 
- **Python environment**: Slow initial setup (10-15+ minutes) - NEVER CANCEL
- **Full test suite**: Very long (can take hours for stress tests) - NEVER CANCEL
- **Integration tests**: Require complex infrastructure setup

### Development Workflow
- **Always validate**: Run lints and builds after changes
- **Frontend changes**: Trigger pre-commit hook automatically
- **CLI changes**: Test basic functionality with `sam --help`  
- **Configuration changes**: Validate YAML generation with CLI commands

## Repository-Specific Commands

### Quick Status Check
```bash
# Check repo structure
ls -la  # Should see: cli/, src/, client/, tests/, docs/, pyproject.toml

# Test basic CLI (may need dependencies)
PYTHONPATH=cli:src python3 cli/main.py --version

# Test frontend
cd client/webui/frontend && npm run lint
```

### Common File Paths
- **Main CLI entry**: `cli/main.py`
- **Core framework**: `src/solace_agent_mesh/`
- **Frontend app**: `client/webui/frontend/src/`
- **Unit tests**: `tests/unit/`
- **Integration tests**: `tests/integration/`  
- **Build config**: `pyproject.toml`, `client/webui/frontend/package.json`
- **CI workflows**: `.github/workflows/ci.yaml`, `.github/workflows/ui-ci.yml`

## Plugin Ecosystem and Deployment

### Plugin Management
- **Add Plugin**: `sam plugin add <plugin-name>` - Installs and configures community plugins
- **Available Plugin Types**: Agents, Gateways, Tools, Service Providers
- **Core Plugins**: Official plugins for Event Mesh Gateway, specialized agents, and integrations
- **Custom Plugins**: Create reusable components with `sam plugin create`

### Deployment Patterns
- **Single Process**: `sam run` - All components in one multi-threaded application
- **Isolated Components**: `sam run configs/agents/my_agent.yaml configs/gateways/webui.yaml` - Run specific components
- **Docker Deployment**: Official `solace/solace-agent-mesh:latest` image with preset configurations
- **Custom Docker Build**: Extend official image for custom dependencies and plugins

### Environment Configuration
```bash
# Core LLM settings
LLM_SERVICE_ENDPOINT=<your-llm-endpoint>
LLM_SERVICE_API_KEY=<your-llm-api-key>
LLM_SERVICE_PLANNING_MODEL_NAME=<planning-model>
LLM_SERVICE_GENERAL_MODEL_NAME=<general-model>

# Web UI settings  
FASTAPI_HOST=0.0.0.0  # Required for Docker deployments
FASTAPI_PORT=8000

# Broker configuration
SOLACE_BROKER_URL=<broker-url>
SOLACE_BROKER_VPN=<vpn-name>
SOLACE_BROKER_USERNAME=<username>
SOLACE_BROKER_PASSWORD=<password>
```

## Debugging and Troubleshooting

### Common Debugging Approaches
- **Isolate Components**: Run specific configs only: `sam run configs/agents/my_tool.yaml`
- **Debug Mode**: Use IDE breakpoints with `module: solace_agent_mesh.cli.main`
- **STIM Files**: Examine stimulus lifecycle traces in storage location
- **Broker Monitoring**: Monitor message flows via Solace broker observability tools

### VSCode Debug Configuration
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "sam-debug",
      "type": "debugpy", 
      "request": "launch",
      "module": "solace_agent_mesh.cli.main",
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env",
      "args": ["run", "configs/agents/main_orchestrator.yaml", "configs/gateways/webui.yaml"],
      "justMyCode": false
    }
  ]
}
```

### Direct Agent Testing
- **Web UI**: Select specific agent in dropdown for direct testing
- **A2A Protocol**: Send direct messages to agent topics using Solace Try Me tools
- **Topic Format**: `{namespace}/a2a/v1/agent/request/<agent_name>`
- **Required Headers**: `userId`, `clientId`, `replyTo`, `a2aUserConfig`

## Tutorial Workflows and Integration Patterns

### Common Tutorial Scenarios
- **SQL Database Integration**: Add SQL agent plugin, configure database connections, query data with natural language
- **RAG (Retrieval Augmented Generation)**: Configure vector databases, embedding models, and knowledge retrieval agents
- **MongoDB Integration**: Connect to MongoDB, perform document queries and aggregations
- **MCP Integration**: Add Model Context Protocol servers as tools for extended capabilities  
- **Custom Agent Creation**: Build specialized agents with custom tools and domain knowledge
- **Event Mesh Gateway**: External broker connectivity with message transformation
- **Slack Integration**: Team collaboration through Slack bot interface
- **Bedrock Agents**: Integration with AWS Bedrock agent services

### Agent Card Configuration
Essential for agent discovery and interoperability:
```yaml
agent_card:
  description: "AI agent for data analysis and reporting"
  defaultInputModes: ["text/plain", "application/json", "file"]
  defaultOutputModes: ["text", "file"] 
  skills:
  - id: "data_analysis"
    name: "Data Analysis"
    description: "Analyzes data using SQL queries and generates visualizations"
  - id: "chart_generation"
    name: "Chart Generation"
    description: "Creates interactive charts from data using Plotly"
```

## Repository-Specific Commands

### Quick Status Check
```bash
# Check repo structure
ls -la  # Should see: cli/, src/, client/, tests/, docs/, pyproject.toml

# Test basic CLI (may need dependencies)
PYTHONPATH=cli:src python3 cli/main.py --version

# Test frontend
cd client/webui/frontend && npm run lint
```

### Common File Paths
- **Main CLI entry**: `cli/main.py`
- **Core framework**: `src/solace_agent_mesh/`
- **Frontend app**: `client/webui/frontend/src/`
- **Unit tests**: `tests/unit/`
- **Integration tests**: `tests/integration/`  
- **Build config**: `pyproject.toml`, `client/webui/frontend/package.json`
- **CI workflows**: `.github/workflows/ci.yaml`, `.github/workflows/ui-ci.yml`