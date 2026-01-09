# Skill: Create and Manage Agents in Solace Agent Mesh

## Skill ID
`create-and-manage-agents`

## Description
Create, configure, and manage AI agents in Solace Agent Mesh. This skill covers agent creation using CLI, agent configuration (instructions, models, tools), agent cards and skills, agent discovery, A2A communication, and lifecycle management.

## Prerequisites
- Initialized Agent Mesh project (see `skill-initialize-project`)
- Configured shared settings (see `skill-configure-shared-settings`)
- Understanding of agent concepts and architecture
- LLM API access configured

## Related Skills
- `initialize-agent-mesh-project` - Project setup
- `configure-shared-settings` - Shared configuration management
- `configure-agent-tools` - Adding tools to agents
- `manage-plugins` - Using plugin-based agents

---

## Why Use This Skill?

**Business Value:**
- **Specialized Expertise**: Create agents for specific business domains
- **Scalability**: Add capabilities without rewriting core systems
- **Flexibility**: Adapt to changing business needs quickly
- **Collaboration**: Multiple agents work together on complex tasks
- **Efficiency**: Automate repetitive tasks with intelligent agents

**Technical Benefits:**
- Modular architecture
- Agent-to-agent communication
- Skill-based discovery
- Lifecycle management
- Context preservation

## When to Use This Skill?

**Use This Skill When:**
- ✅ Building specialized AI capabilities (data analysis, API integration, etc.)
- ✅ Creating multi-agent systems with division of labor
- ✅ Implementing domain-specific expertise
- ✅ Scaling beyond single-agent limitations
- ✅ Adding new capabilities to existing mesh

**Skip This Skill When:**
- ❌ Project not yet initialized (do that first)
- ❌ Just need to modify existing agent (edit YAML directly)
- ❌ Only need gateway changes

**Decision Points:**
- **Single task?** → Create focused specialist agent
- **Complex workflow?** → Create orchestrator + specialist agents
- **External API?** → Create API integration agent
- **Data processing?** → Create data analysis agent
- **Multi-modal needs?** → Create multimodal agent with image/audio tools

---

## Core Concepts

### What is an Agent?

An agent in Solace Agent Mesh is an AI-powered processing unit that:

1. **Processes Tasks**: Executes specific functions or provides domain expertise
2. **Uses Tools**: Accesses capabilities like database queries, API calls, file operations
3. **Communicates**: Interacts with other agents via A2A protocol
4. **Maintains Context**: Remembers conversation history through session management
5. **Manages Artifacts**: Creates and handles files and data

### Agent Architecture

```
┌─────────────────────────────────────┐
│           Agent                      │
├─────────────────────────────────────┤
│  • LLM Model (Planning/General)     │
│  • System Instructions              │
│  • Tool Registry                    │
│  • Session Management               │
│  • Artifact Service                 │
│  • Agent Card (Identity)            │
└─────────────────────────────────────┘
         │
         ├──> A2A Protocol (Event Mesh)
         ├──> Tools (Built-in, Custom, MCP)
         └──> Storage (Sessions, Artifacts)
```

### Agent Lifecycle

1. **Initialization**: Load configuration, connect to broker, initialize services
2. **Discovery**: Broadcast agent card to announce capabilities
3. **Active**: Listen for messages, process tasks, use tools
4. **Execution**: Work on tasks, delegate to other agents if needed
5. **Cleanup**: Graceful shutdown, close connections, save state

---

## Step-by-Step Instructions

### Method 1: Create Agent with Browser GUI (Recommended)

The easiest way to create a well-configured agent.

#### Step 1: Launch Agent Creation GUI

```bash
sam add agent my-agent --gui
```

**Expected Output:**
```
Starting agent configuration portal...
Configuration portal available at: http://127.0.0.1:5002
Opening browser...
```

#### Step 2: Configure in Browser

The browser interface guides you through:

1. **Basic Information**
   - Agent name
   - Namespace
   - Display name
   - Description

2. **Model Configuration**
   - Model type (planning, general, multimodal)
   - Custom model settings
   - Streaming support

3. **Instructions**
   - System prompt
   - Agent personality
   - Task guidelines

4. **Tools Configuration**
   - Built-in tool groups
   - Custom tools
   - MCP tools

5. **Storage Configuration**
   - Session service
   - Artifact service
   - Data tools config

6. **Agent Card**
   - Description
   - Input/output modes
   - Skills definition

7. **Discovery Settings**
   - Enable/disable discovery
   - Publishing interval
   - Communication settings

#### Step 3: Save Configuration

Click "Create Agent" to generate the configuration file at:
```
configs/agents/my_agent.yaml
```

---

### Method 2: Create Agent with Interactive CLI

Terminal-based agent creation.

#### Step 1: Start Interactive Creation

```bash
sam add agent my-agent
```

#### Step 2: Answer Prompts

```
? Namespace: myorg/dev
? Enable streaming support? (Y/n): Y
? Model type:
  1. Planning model
  2. General model
  3. Multimodal model
? Custom instruction: You are a helpful assistant that...
? Session service type:
  1. Memory
  2. SQL
? Artifact service type:
  1. Memory
  2. Filesystem
  3. GCS
? Enable built-in artifact tools? (Y/n): Y
? Enable built-in data tools? (Y/n): Y
? Enable agent discovery? (Y/n): Y
```

#### Step 3: Verify Creation

```bash
ls configs/agents/my_agent.yaml
cat configs/agents/my_agent.yaml
```

---

### Method 3: Create Agent Non-Interactively

For automation and scripting.

```bash
sam add agent my-agent \
  --skip \
  --namespace "myorg/production" \
  --supports-streaming \
  --model-type planning \
  --instruction "You are a specialized data analysis agent..." \
  --session-service-type sql \
  --artifact-service-type filesystem \
  --artifact-service-base-path "/var/lib/agent-mesh/artifacts" \
  --enable-builtin-artifact-tools \
  --enable-builtin-data-tools \
  --agent-discovery-enabled \
  --agent-card-description "Data analysis specialist" \
  --agent-card-default-input-modes-str "text,file" \
  --agent-card-default-output-modes-str "text,file"
```

---

## Agent Configuration Structure

### Complete Agent Configuration Template

```yaml
apps:
  - name: my-agent
    app_module: solace_agent_mesh.agent.sac.app
    
    # Broker connection (from shared config)
    broker:
      <<: *broker_connection
    
    # Agent-specific configuration
    app_config:
      # Basic Identity
      namespace: ${NAMESPACE}
      agent_name: "my-agent"
      display_name: "My Specialized Agent"
      supports_streaming: true
      
      # LLM Model Configuration
      model: *planning_model
      
      # System Instructions
      instruction: |
        You are a specialized agent that performs specific tasks.
        Your capabilities include:
        1. Task A
        2. Task B
        3. Task C
        
        Always be clear and concise in your responses.
      
      # Tools Configuration
      tools:
        # Built-in tool groups
        - tool_type: builtin-group
          group_name: "artifact_management"
        
        - tool_type: builtin-group
          group_name: "data_analysis"
        
        # Custom Python tool
        - tool_type: python
          component_module: "my_agent.tools"
          function_name: "my_custom_tool"
          tool_config:
            api_key: ${MY_API_KEY}
      
      # Agent Card (Public Profile)
      agent_card:
        description: "A specialized agent for specific tasks"
        defaultInputModes: ["text", "file"]
        defaultOutputModes: ["text", "file"]
        skills:
          - id: "data_analysis"
            name: "Data Analysis"
            description: "Analyze and visualize data"
          - id: "file_processing"
            name: "File Processing"
            description: "Process and transform files"
      
      # Discovery Configuration
      agent_discovery_enabled: true
      agent_card_publishing_interval: 30
      
      # Inter-Agent Communication
      inter_agent_communication:
        allow_list: ["*"]  # Allow all agents
        deny_list: []
        timeout: 300
      
      # Storage Services
      session_service: *default_session_service
      artifact_service: *default_artifact_service
      
      # Lifecycle Functions (optional)
      agent_init_function:
        module: "my_agent.lifecycle"
        name: "initialize_agent"
        base_path: "src"
        config:
          startup_message: "Agent starting..."
      
      agent_cleanup_function:
        module: "my_agent.lifecycle"
        name: "cleanup_agent"
        base_path: "src"
```

---

## Common Agent Patterns

### Pattern 1: Data Analysis Agent

**Use Case:** Agent specialized in querying databases and creating visualizations

```yaml
app_config:
  agent_name: "data-analyst"
  
  instruction: |
    You are a data analysis specialist. You can:
    - Query SQL databases
    - Transform data with jq
    - Create visualizations with Plotly
    - Generate reports
    
    Always explain your analysis clearly.
  
  tools:
    - tool_type: builtin-group
      group_name: "data_analysis"
    
    - tool_type: builtin-group
      group_name: "artifact_management"
  
  agent_card:
    description: "Data analysis and visualization specialist"
    skills:
      - id: "query_data_with_sql"
        name: "SQL Query"
        description: "Query databases with SQL"
      - id: "create_chart_from_plotly_config"
        name: "Create Charts"
        description: "Generate visualizations"
```

---

### Pattern 2: API Integration Agent

**Use Case:** Agent that interacts with external APIs

```yaml
app_config:
  agent_name: "api-connector"
  
  instruction: |
    You are an API integration specialist. You can:
    - Make HTTP requests to external APIs
    - Parse and transform API responses
    - Handle authentication
    - Retry failed requests
  
  tools:
    - tool_type: builtin-group
      group_name: "web"
    
    - tool_type: python
      component_module: "my_agent.api_tools"
      function_name: "call_external_api"
      tool_config:
        api_base_url: ${EXTERNAL_API_URL}
        api_key: ${EXTERNAL_API_KEY}
        timeout: 30
  
  agent_card:
    description: "External API integration specialist"
    skills:
      - id: "web_request"
        name: "Web Request"
        description: "Make HTTP requests"
      - id: "call_external_api"
        name: "External API"
        description: "Call specific external API"
```

---

### Pattern 3: Document Processing Agent

**Use Case:** Agent that processes and transforms documents

```yaml
app_config:
  agent_name: "doc-processor"
  
  instruction: |
    You are a document processing specialist. You can:
    - Convert files to markdown
    - Extract text from PDFs
    - Generate summaries
    - Create structured data from documents
  
  tools:
    - tool_type: builtin-group
      group_name: "artifact_management"
    
    - tool_type: builtin
      tool_name: "convert_file_to_markdown"
    
    - tool_type: python
      component_module: "my_agent.doc_tools"
      function_name: "extract_pdf_text"
  
  agent_card:
    description: "Document processing and transformation specialist"
    defaultInputModes: ["text", "file"]
    defaultOutputModes: ["text", "file"]
    skills:
      - id: "convert_file_to_markdown"
        name: "Convert to Markdown"
        description: "Convert various file formats to markdown"
      - id: "extract_pdf_text"
        name: "Extract PDF Text"
        description: "Extract text content from PDF files"
```

---

### Pattern 4: Orchestrator Agent

**Use Case:** Main agent that coordinates other specialized agents

```yaml
app_config:
  agent_name: "main-orchestrator"
  
  instruction: |
    You are the main orchestrator agent. Your role is to:
    - Understand user requests
    - Delegate tasks to specialized agents
    - Coordinate multi-step workflows
    - Synthesize results from multiple agents
    
    Available specialized agents:
    - data-analyst: For data analysis tasks
    - api-connector: For external API calls
    - doc-processor: For document processing
  
  tools:
    # Peer-to-peer delegation is built-in
    - tool_type: builtin-group
      group_name: "artifact_management"
  
  inter_agent_communication:
    allow_list: ["data-analyst", "api-connector", "doc-processor"]
    timeout: 600
  
  agent_card:
    description: "Main orchestrator coordinating specialized agents"
    skills:
      - id: "task_coordination"
        name: "Task Coordination"
        description: "Coordinate complex multi-agent workflows"
```

---

### Pattern 5: Multimodal Agent

**Use Case:** Agent that handles text, images, and audio

```yaml
app_config:
  agent_name: "multimodal-agent"
  
  model: *multimodal_model
  
  instruction: |
    You are a multimodal AI assistant. You can:
    - Analyze images and describe their content
    - Generate images from descriptions
    - Transcribe audio files
    - Convert text to speech
    - Process multiple media types together
  
  tools:
    - tool_type: builtin-group
      group_name: "image"
    
    - tool_type: builtin-group
      group_name: "audio"
    
    - tool_type: builtin-group
      group_name: "artifact_management"
  
  agent_card:
    description: "Multimodal AI assistant for text, image, and audio"
    defaultInputModes: ["text", "image", "audio", "file"]
    defaultOutputModes: ["text", "image", "audio", "file"]
    skills:
      - id: "describe_image"
        name: "Image Analysis"
        description: "Analyze and describe images"
      - id: "create_image_from_description"
        name: "Image Generation"
        description: "Generate images from text descriptions"
      - id: "transcribe_audio"
        name: "Audio Transcription"
        description: "Transcribe audio to text"
```

---

## Agent Card Configuration

### Understanding Agent Cards

The agent card is the public profile that describes an agent's capabilities. It's crucial for:

- **Discovery**: Other agents find and understand capabilities
- **Routing**: Gateways and orchestrators know when to use this agent
- **Documentation**: Users understand what the agent can do

### Agent Card Structure

```yaml
agent_card:
  # Brief description of agent's purpose
  description: "A specialized agent for X, Y, and Z tasks"
  
  # Supported input formats
  defaultInputModes:
    - "text"      # Plain text
    - "file"      # File uploads
    - "image"     # Image files
    - "audio"     # Audio files
    - "application/json"  # JSON data
  
  # Supported output formats
  defaultOutputModes:
    - "text"
    - "file"
    - "image"
  
  # Detailed skill definitions
  skills:
    - id: "skill_identifier"
      name: "Human Readable Name"
      description: "Detailed description of what this skill does"
```

### Skill Definition Best Practices

1. **Match Tool Names**: Skill IDs should match tool names
2. **Clear Descriptions**: Help LLMs understand when to use the skill
3. **Specific Capabilities**: List concrete actions, not vague abilities

**Good Example:**
```yaml
skills:
  - id: "query_data_with_sql"
    name: "SQL Database Query"
    description: "Execute SQL queries against connected databases. Supports SELECT, JOIN, aggregations, and complex queries. Returns results as structured data."
```

**Bad Example:**
```yaml
skills:
  - id: "data_stuff"
    name: "Data"
    description: "Does data things"
```

---

## Agent Discovery and Communication

### Enable Agent Discovery

```yaml
app_config:
  # Enable discovery
  agent_discovery_enabled: true
  
  # How often to broadcast agent card (seconds)
  agent_card_publishing_interval: 30
```

### Configure Inter-Agent Communication

```yaml
app_config:
  inter_agent_communication:
    # Allow all agents
    allow_list: ["*"]
    
    # Or specify specific agents
    # allow_list: ["agent1", "agent2", "agent3"]
    
    # Deny specific agents
    deny_list: ["untrusted-agent"]
    
    # Timeout for agent-to-agent calls (seconds)
    timeout: 300
```

### Communication Patterns

**Allow All (Default):**
```yaml
allow_list: ["*"]
deny_list: []
```

**Whitelist Specific Agents:**
```yaml
allow_list: ["data-analyst", "api-connector"]
deny_list: []
```

**Blacklist Specific Agents:**
```yaml
allow_list: ["*"]
deny_list: ["test-agent", "deprecated-agent"]
```

---

## Agent Lifecycle Management

### Initialization Function

Create `src/my_agent/lifecycle.py`:

```python
from typing import Any
from pydantic import BaseModel, Field
from solace_ai_connector.common.log import log

class AgentInitConfig(BaseModel):
    """Configuration for agent initialization."""
    startup_message: str = Field(description="Message to log on startup")
    api_key: str = Field(description="API key for external service")

async def initialize_agent(host_component: Any, init_config: AgentInitConfig):
    """Initialize the agent with required resources."""
    log_id = f"[{host_component.agent_name}:init]"
    log.info(f"{log_id} {init_config.startup_message}")
    
    # Initialize external connections
    api_client = create_api_client(init_config.api_key)
    
    # Store in agent state
    host_component.set_agent_specific_state("api_client", api_client)
    host_component.set_agent_specific_state("request_count", 0)
    
    log.info(f"{log_id} Agent initialized successfully")

async def cleanup_agent(host_component: Any):
    """Clean up agent resources on shutdown."""
    log_id = f"[{host_component.agent_name}:cleanup]"
    log.info(f"{log_id} Starting cleanup...")
    
    # Retrieve and close connections
    api_client = host_component.get_agent_specific_state("api_client")
    if api_client:
        await api_client.close()
    
    # Log statistics
    count = host_component.get_agent_specific_state("request_count", 0)
    log.info(f"{log_id} Processed {count} requests")
    
    log.info(f"{log_id} Cleanup completed")
```

### Configure Lifecycle in YAML

```yaml
app_config:
  agent_init_function:
    module: "my_agent.lifecycle"
    name: "initialize_agent"
    base_path: "src"
    config:
      startup_message: "Starting my agent..."
      api_key: ${EXTERNAL_API_KEY}
  
  agent_cleanup_function:
    module: "my_agent.lifecycle"
    name: "cleanup_agent"
    base_path: "src"
```

---

## Managing Multiple Agents

### Organize Agent Configurations

```
configs/agents/
├── orchestrator.yaml          # Main coordinator
├── data_analyst.yaml          # Data analysis specialist
├── api_connector.yaml         # API integration
├── doc_processor.yaml         # Document processing
└── shared/
    ├── common_tools.yaml      # Shared tool configs
    └── common_settings.yaml   # Shared agent settings
```

### Run Specific Agents

```bash
# Run single agent
sam run configs/agents/data_analyst.yaml

# Run multiple specific agents
sam run configs/agents/orchestrator.yaml configs/agents/data_analyst.yaml

# Run all agents
sam run configs/agents/
```

### Agent Naming Conventions

**Good Practices:**
- Use descriptive names: `data-analyst`, `api-connector`
- Use hyphens for multi-word names
- Include purpose: `customer-support-agent`, `sales-assistant`
- Avoid generic names: `agent1`, `test`, `my-agent`

---

## Troubleshooting

### Issue: Agent not discovered by other agents

**Symptoms:**
- Agent starts successfully
- Other agents can't find or communicate with it

**Solutions:**

1. **Enable discovery:**
```yaml
agent_discovery_enabled: true
```

2. **Check publishing interval:**
```yaml
agent_card_publishing_interval: 30  # Seconds
```

3. **Verify agent card:**
```yaml
agent_card:
  description: "Must have description"
  skills:
    - id: "must_have_skills"
```

4. **Check broker connection:**
```bash
# Verify agent is connected
# Check broker logs or PubSub+ Manager
```

---

### Issue: Agent can't use tools

**Symptoms:**
```
Error: Tool 'my_tool' not found
```

**Solutions:**

1. **Verify tool configuration:**
```yaml
tools:
  - tool_type: python
    component_module: "my_agent.tools"
    function_name: "my_tool"
```

2. **Check module path:**
```bash
# Verify file exists
ls src/my_agent/tools.py

# Test import
python -c "from my_agent.tools import my_tool"
```

3. **Add base_path if needed:**
```yaml
tools:
  - tool_type: python
    component_module: "my_agent.tools"
    component_base_path: "src"
```

---

### Issue: Agent uses wrong model

**Symptoms:**
- Agent behavior doesn't match expected model
- Costs are higher/lower than expected

**Solutions:**

1. **Verify model configuration:**
```yaml
model: *planning_model  # Check anchor reference
```

2. **Check shared config:**
```bash
grep -A 5 "planning_model" configs/shared_config.yaml
```

3. **Verify environment variables:**
```bash
echo $LLM_SERVICE_PLANNING_MODEL_NAME
```

---

### Issue: Inter-agent communication fails

**Symptoms:**
```
Error: Agent 'target-agent' not reachable
Timeout waiting for response
```

**Solutions:**

1. **Check allow/deny lists:**
```yaml
inter_agent_communication:
  allow_list: ["target-agent"]  # Must include target
  deny_list: []  # Must not include target
```

2. **Increase timeout:**
```yaml
inter_agent_communication:
  timeout: 600  # Increase from default 300
```

3. **Verify target agent is running:**
```bash
ps aux | grep "target-agent"
```

4. **Check broker connectivity:**
```bash
# Both agents must be connected to same broker
```

---

## Best Practices

### Agent Design

1. **Single Responsibility**: Each agent should have a clear, focused purpose
2. **Clear Instructions**: Write detailed system prompts explaining capabilities
3. **Appropriate Tools**: Only include tools the agent actually needs
4. **Descriptive Names**: Use names that clearly indicate the agent's function

### Configuration

1. **Use Shared Config**: Reference shared settings for consistency
2. **Environment Variables**: Use env vars for sensitive data and environment-specific settings
3. **Document Skills**: Write clear, detailed skill descriptions
4. **Version Control**: Track agent configurations in git

### Performance

1. **Choose Right Model**: Use planning model for complex tasks, general for simple ones
2. **Enable Caching**: Use prompt caching for repeated patterns
3. **Parallel Tools**: Enable parallel tool calls when possible
4. **Optimize Instructions**: Keep system prompts concise but complete

### Security

1. **Limit Communication**: Use allow/deny lists to control agent interactions
2. **Secure Credentials**: Never hardcode API keys or passwords
3. **Validate Inputs**: Implement input validation in custom tools
4. **Audit Logs**: Enable logging for security monitoring

---

## Validation Checklist

Before deploying an agent:

- [ ] Agent name is descriptive and unique
- [ ] System instructions are clear and complete
- [ ] Model configuration is appropriate for tasks
- [ ] All required tools are configured
- [ ] Agent card has description and skills
- [ ] Discovery settings are configured
- [ ] Inter-agent communication is properly restricted
- [ ] Storage services are configured
- [ ] Lifecycle functions work correctly
- [ ] Agent starts without errors
- [ ] Agent responds to test requests
- [ ] Agent can communicate with other agents (if needed)

---

## Next Steps

After creating agents:

1. **Add Tools**: Use `skill-configure-agent-tools` to add capabilities
2. **Test Agent**: Send test requests and verify responses
3. **Monitor Performance**: Track response times and resource usage
4. **Create Gateways**: Use `skill-create-and-manage-gateways` for external access
5. **Scale Up**: Add more specialized agents as needed

---

## Additional Resources

- [Agent Documentation](https://docs.cline.bot/components/agents)
- [Creating Custom Agents Tutorial](https://docs.cline.bot/developing/tutorials/custom-agent)
- [Built-in Tools Reference](https://docs.cline.bot/components/builtin-tools/builtin-tools)
- [Agent Development Guide](https://docs.cline.bot/developing/create-agents)