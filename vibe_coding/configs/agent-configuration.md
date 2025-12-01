# Agent Configuration

Defines agent behavior, capabilities, instructions, and tools. Agents are the core processing units in Agent Mesh that execute tasks and collaborate to solve complex problems.

## Overview

Agent configuration specifies:
- **Identity** - Agent name, namespace, and display name
- **Behavior** - System instructions and persona
- **Intelligence** - LLM model selection
- **Capabilities** - Available tools and skills
- **Services** - Session and artifact storage
- **Lifecycle** - Initialization and cleanup functions

## Top-Level Structure

```yaml
components:
  - name: agent-name
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection
    app_config:
      # Agent-specific configuration
```

## app_config Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `namespace` | String | Yes | - | Topic namespace (e.g., `"myorg/prod"`) |
| `agent_name` | String | Yes | - | Unique agent identifier |
| `display_name` | String | No | `agent_name` | Human-readable name |
| `instruction` | String | Yes | - | System prompt defining behavior |
| `model` | Object | Yes | - | LLM model configuration |
| `tools` | List | No | `[]` | Available tools |
| `session_service` | Object | Yes | - | Session storage config |
| `artifact_service` | Object | Yes | - | Artifact storage config |
| `artifact_handling_mode` | String | No | `"reference"` | Artifact handling: `"reference"`, `"embed"`, `"ignore"` |
| `inject_user_profile` | Boolean | No | `false` | Include user profile in context |
| `agent_card` | Object | No | - | Agent metadata |
| `agent_init_function` | Object | No | - | Initialization function |
| `agent_cleanup_function` | Object | No | - | Cleanup function |

## Basic Configuration

### Minimal Agent

```yaml
!include shared_config.yaml

components:
  - name: simple-agent
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      agent_name: "simple-agent"
      
      instruction: "You are a helpful assistant."
      
      model: *general_model
      session_service: *default_session_service
      artifact_service: *default_artifact_service
```

### Complete Agent

```yaml
!include shared_config.yaml

components:
  - name: data-analyst
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      agent_name: "data-analyst"
      display_name: "Data Analyst Agent"
      
      instruction: |
        You are a data analyst agent specialized in analyzing datasets and creating visualizations.
        
        Your capabilities:
        1. Analyze CSV and Excel files
        2. Create charts and graphs
        3. Generate statistical summaries
        4. Provide data insights
        
        Always explain your analysis clearly and provide actionable insights.
      
      model: *general_model
      
      tools:
        - tool_type: builtin-group
          group_name: "data_analysis"
        - tool_type: builtin-group
          group_name: "artifact_management"
      
      session_service: *default_session_service
      artifact_service: *default_artifact_service
      artifact_handling_mode: "reference"
      
      agent_card:
        description: "Analyzes data and creates visualizations"
        defaultInputModes: ["text", "file"]
        defaultOutputModes: ["text", "file"]
        skills:
          - id: "analyze_data"
            name: "Data Analysis"
            description: "Analyze datasets and provide insights"
          - id: "create_visualization"
            name: "Create Visualizations"
            description: "Generate charts and graphs"
```

## Agent Instructions

The `instruction` field is the system prompt that defines agent behavior.

### Writing Effective Instructions

**Be Specific**:
```yaml
instruction: |
  You are a customer support agent for TechCorp.
  
  Your responsibilities:
  - Answer product questions
  - Troubleshoot technical issues
  - Escalate complex problems to human agents
  
  Always be polite, professional, and helpful.
```

**Define Capabilities**:
```yaml
instruction: |
  You are a code review agent.
  
  You can:
  1. Review code for bugs and security issues
  2. Suggest improvements and best practices
  3. Check code style and formatting
  
  You cannot:
  - Execute code
  - Access external systems
  - Make direct code changes
```

**Set Tone and Style**:
```yaml
instruction: |
  You are a friendly teaching assistant.
  
  Communication style:
  - Use simple, clear language
  - Provide examples
  - Encourage questions
  - Be patient and supportive
```

### Multi-Line Instructions

Use YAML multi-line syntax:

```yaml
instruction: |
  Line 1
  Line 2
  Line 3

# Or
instruction: >
  This is a long instruction
  that will be joined into
  a single line.
```

## Artifact Handling Modes

Controls how agents handle file artifacts:

| Mode | Description | Use Case |
|------|-------------|----------|
| `reference` | Store separately, pass URIs | Large files, production (recommended) |
| `embed` | Include content in messages | Small data, simple workflows |
| `auto` | Automatically choose based on size | General purpose |

### Reference Mode (Recommended)

```yaml
artifact_handling_mode: "reference"
```

- Artifacts stored in artifact service
- Only URIs passed in messages
- Efficient for large files
- Supports versioning

### Embed Mode

```yaml
artifact_handling_mode: "embed"
```

- Artifact content included in messages
- Simple for small data
- No separate storage needed
- Limited by message size

### Auto Mode

```yaml
artifact_handling_mode: "ignore"
```

- Automatically chooses based on size
- Small artifacts embedded
- Large artifacts referenced

## User Profile Injection

Include user information in agent context:

```yaml
inject_user_profile: true
```

When enabled, agents receive:
- User ID
- User name
- User email
- User roles/permissions

Use for:
- Personalized responses
- Access control
- User-specific data

## Complete Examples

### Calculator Agent

```yaml
!include shared_config.yaml

components:
  - name: calculator
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      agent_name: "calculator"
      display_name: "Calculator Agent"
      
      instruction: |
        You are a calculator agent that performs mathematical operations.
        
        Available operations:
        - Addition
        - Subtraction
        - Division
        - Multiplication
        
        Always show your work and explain the calculation.
      
      model: *general_model
      
      tools:
        - tool_type: python
          component_module: "calculator_plugin.tools"
          function_name: "add_numbers"
        - tool_type: python
          component_module: "calculator_plugin.tools"
          function_name: "subtract_numbers"
        - tool_type: python
          component_module: "calculator_plugin.tools"
          function_name: "divide_numbers"
      
      session_service: *default_session_service
      artifact_service: *default_artifact_service
```

### Orchestrator Agent

```yaml
!include shared_config.yaml

components:
  - name: orchestrator
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      agent_name: "OrchestratorAgent"
      display_name: "Main Orchestrator"
      
      instruction: |
        You are the main orchestrator agent that coordinates tasks across specialized agents.
        
        Your role:
        1. Understand user requests
        2. Break down complex tasks
        3. Delegate to appropriate agents
        4. Aggregate results
        5. Provide comprehensive responses
        
        Available agents:
        - data-analyst: Data analysis and visualization
        - calculator: Mathematical operations
        - file-processor: File conversion and processing
      
      model: *planning_model  # Use higher-quality model for orchestration
      
      tools:
        - tool_type: builtin-group
          group_name: "artifact_management"
      
      session_service:
        type: "sql"
        database_url: "${DATABASE_URL}"
        default_behavior: "PERSISTENT"
      
      artifact_service: *default_artifact_service
      artifact_handling_mode: "reference"
      inject_user_profile: true
```

### Multimodal Agent

```yaml
!include shared_config.yaml

components:
  - name: image-analyzer
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      agent_name: "image-analyzer"
      display_name: "Image Analyzer"
      
      instruction: |
        You are an image analysis agent that can understand and describe images.
        
        Capabilities:
        - Describe image content
        - Identify objects and people
        - Analyze image composition
        - Extract text from images
        - Generate image descriptions
      
      model: *multimodal_model
      
      tools:
        - tool_type: builtin-group
          group_name: "artifact_management"
        - tool_type: python
          component_module: "image_tools.tools"
          function_name: "analyze_image"
      
      session_service: *default_session_service
      artifact_service: *default_artifact_service
      
      agent_card:
        description: "Analyzes and describes images"
        defaultInputModes: ["text", "image"]
        defaultOutputModes: ["text"]
```

## Agent Naming Conventions

### agent_name

- Use lowercase with hyphens
- Be descriptive and unique
- Examples: `calculator`, `data-analyst`, `customer-support`

### display_name

- Use proper capitalization
- Human-readable
- Examples: `Calculator Agent`, `Data Analyst`, `Customer Support`

### namespace

- Use organization/environment pattern
- Examples: `myorg/prod`, `company/staging`, `team/dev`

## Best Practices

### 1. Clear Instructions

Write detailed, specific instructions:

```yaml
instruction: |
  You are a [role] that [primary function].
  
  Your capabilities:
  1. [Capability 1]
  2. [Capability 2]
  
  Guidelines:
  - [Guideline 1]
  - [Guideline 2]
```

### 2. Appropriate Model Selection

Choose models based on task complexity:

```yaml
# Simple tasks
model: *general_model

# Complex reasoning
model: *planning_model

# Image/audio processing
model: *multimodal_model
```

### 3. Tool Organization

Group related tools:

```yaml
tools:
  # Data tools
  - tool_type: builtin-group
    group_name: "data_analysis"
  
  # File tools
  - tool_type: builtin-group
    group_name: "artifact_management"
  
  # Custom tools
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "custom_tool"
```

### 4. Service Configuration

Use appropriate storage:

```yaml
# Development
session_service:
  type: "memory"

# Production
session_service:
  type: "sql"
  database_url: "${DATABASE_URL}"
```

### 5. Agent Cards

Always include agent cards for discoverability:

```yaml
agent_card:
  description: "Clear description of agent purpose"
  defaultInputModes: ["text", "file"]
  defaultOutputModes: ["text", "file"]
  skills:
    - id: "skill_id"
      name: "Skill Name"
      description: "What this skill does"
```

## Troubleshooting

### Agent Not Responding

**Solutions**:
1. Check broker connection
2. Verify namespace matches
3. Review agent logs
4. Test with simple request

### Tool Execution Fails

**Solutions**:
1. Verify tool configuration
2. Check tool module path
3. Review tool logs
4. Test tool independently

### Model Errors

**Solutions**:
1. Verify API key is set
2. Check model identifier
3. Review rate limits
4. Test model connection

### Session/Artifact Issues

**Solutions**:
1. Verify service configuration
2. Check storage accessibility
3. Review service logs
4. Test storage independently

## Related Documentation

- [Tool Configuration](./tool-configuration.md) - Configuring agent tools
- [Model Configuration](./model-configuration.md) - LLM model setup
- [Service Configuration](./service-configuration.md) - Storage services
- [Agent Card Configuration](./agent-card-configuration.md) - Agent metadata
- [Lifecycle Functions](./lifecycle-functions.md) - Init and cleanup
- [Best Practices](./best-practices.md) - Configuration guidelines