# Calculator Agent for Solace Agent Mesh

A specialized AI agent that performs addition calculations using the Solace Agent Mesh (SAM) framework. This agent demonstrates how to create a simple, focused agent with custom tools for mathematical operations.

## Features

- **Addition Operations**: Performs accurate addition of two numbers
- **Support for Different Number Types**: Handles integers, decimals, and negative numbers
- **Error Handling**: Robust validation and error reporting for invalid inputs
- **Natural Language Interface**: Responds to conversational requests like "add 5 and 3" or "what is 2.5 + 7.1?"
- **A2A Protocol Integration**: Discoverable by other agents in the mesh for delegation
- **Artifact Storage**: Results can be saved as artifacts for later use

## Architecture

The calculator agent consists of:

1. **Custom Calculator Tool** (`add_two_numbers`): Core mathematical function with input validation
2. **Agent Configuration**: YAML configuration defining behavior, tools, and capabilities  
3. **SAM Framework Integration**: A2A protocol support, session management, and artifact handling

## Installation and Setup

### Prerequisites

- Python 3.10+ with Solace Agent Mesh framework installed
- Access to a Solace PubSub+ broker
- LLM service endpoint configured

### Environment Configuration

Ensure these environment variables are set in your `.env` file:

```bash
# Agent namespace
NAMESPACE=local

# Solace Broker Configuration  
SOLACE_BROKER_URL=tcps://your-broker-url:55443
SOLACE_BROKER_USERNAME=your-username
SOLACE_BROKER_PASSWORD=your-password
SOLACE_BROKER_VPN=your-vpn

# LLM Service Configuration
LLM_SERVICE_ENDPOINT=https://your-llm-endpoint/
LLM_SERVICE_API_KEY=your-api-key
LLM_SERVICE_PLANNING_MODEL_NAME=openai/vertex-claude-4-5-sonnet
LLM_SERVICE_GENERAL_MODEL_NAME=openai/vertex-claude-4-5-sonnet
```

### Installation Steps

1. **Clone the repository** (if using the example):
   ```bash
   git clone <repository-url>
   cd solace-agent-mesh
   ```

2. **Set up Python environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\\Scripts\\activate  # On Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   # or using hatch:
   hatch env create
   ```

## Configuration

The calculator agent is configured via `examples/agents/calculator_agent.yaml`:

### Key Configuration Sections

**Agent Identity:**
```yaml
agent_name: "CalculatorAgent"
display_name: "Calculator" 
namespace: ${NAMESPACE}
```

**Custom Tool Integration:**
```yaml
tools:
  - tool_type: python
    tool_name: "add_two_numbers"
    component_module: "examples.sample_tools"
    function_name: "add_two_numbers"
```

**Agent Capabilities:**
```yaml
agent_card:
  description: |
    Calculator agent specialized in addition operations. 
    Use this agent when you need to add two numbers together.
  skills:
    - id: "addition"
      name: "Addition Calculator"
      description: "Performs addition of two numbers with support for integers, decimals, and negative values"
```

## Running the Agent

### Start the Calculator Agent

```bash
# Activate virtual environment
source .venv/bin/activate

# Set Python path
export PYTHONPATH=cli:src

# Run the calculator agent
python cli/main.py run examples/agents/calculator_agent.yaml
```

The agent will:
1. Connect to the Solace broker
2. Load the `add_two_numbers` tool  
3. Start listening for requests on topic: `{namespace}/a2a/v1/agent/request/CalculatorAgent`
4. Publish its agent card every 10 seconds for discovery

### Verify Agent is Running

Look for these log messages indicating successful startup:
```
INFO | Successfully connected to broker at [broker-url]
INFO | Loaded Python tool: add_two_numbers from examples.sample_tools
INFO | ADK Agent 'CalculatorAgent' created. Callbacks assigned.
INFO | Async initialization completed successfully.
```

## Usage Examples

### Direct Agent Interaction

You can interact with the calculator agent through:

1. **Web UI Gateway** (if running):
   - Select "Calculator" from the agent dropdown
   - Enter requests like: "Add 15 and 27" or "What is 3.14 + 2.86?"

2. **A2A Protocol Messages** (for other agents):
   ```json
   {
     "message": {
       "role": "user", 
       "parts": [
         {"type": "text", "text": "Please calculate 42 + 58"}
       ]
     }
   }
   ```

### Example Interactions

**Simple Addition:**
```
User: "Add 5 and 3"
Agent: "I'll calculate 5 + 3 for you. The result is 8."
```

**Decimal Numbers:**
```  
User: "What is 2.5 plus 7.1?"
Agent: "I'll add 2.5 and 7.1. The result is 9.6."
```

**Negative Numbers:**
```
User: "Calculate -10 + 15"  
Agent: "I'll calculate -10 + 15 for you. The result is 5."
```

**Error Handling:**
```
User: "Add hello and 5"
Agent: "I encountered an error: Invalid input types. Expected numbers, got str and int."
```

## Tool Function Details

The core `add_two_numbers` function in `examples/sample_tools.py`:

```python
def add_two_numbers(number1: float, number2: float) -> dict:
    """
    Calculator tool that adds two numbers together.
    
    Args:
        number1: The first number to add
        number2: The second number to add
        
    Returns:
        Dictionary with status, result, and metadata
    """
```

**Return Format:**
```python
{
    "status": "success",
    "message": "Successfully added 5.0 + 3.0", 
    "result": 8.0,
    "operation": "addition",
    "operands": [5.0, 3.0]
}
```

## Testing and Validation

### Manual Testing

1. **Start the agent** as described above
2. **Send test requests** through available gateways
3. **Verify responses** contain correct calculations
4. **Test error cases** with invalid inputs

### Integration with Other Agents

The calculator agent can be discovered and used by other agents:

```python
# From another agent's tools
peer_tool = PeerAgentTool("CalculatorAgent", component)
result = await peer_tool.run_async({
    "task_description": "Add 10 and 20",
    "number1": 10,
    "number2": 20
})
```

## Troubleshooting

### Common Issues

**Agent fails to start:**
- Check broker connection settings in `.env`
- Verify LLM service credentials are correct
- Ensure Python path includes `cli:src`

**Tool loading errors:**
- Verify `examples/sample_tools.py` contains `add_two_numbers` function
- Check that `component_module` and `function_name` match exactly

**Connection issues:**
- Confirm Solace broker URL and credentials
- Check network connectivity to broker
- Verify VPN settings if applicable

### Debug Mode

Run with verbose logging:
```bash
python cli/main.py run examples/agents/calculator_agent.yaml --log-level DEBUG
```

### Log Files

Agent logs are written to `calculator_agent.log` with detailed operation traces.

## Customization

### Adding More Operations

To extend the calculator with more operations:

1. **Add functions to `sample_tools.py`**:
   ```python
   def subtract_two_numbers(number1: float, number2: float) -> dict:
       # Implementation here
   ```

2. **Update agent configuration**:
   ```yaml
   tools:
     - tool_type: python
       tool_name: "subtract_two_numbers"
       component_module: "examples.sample_tools"
       function_name: "subtract_two_numbers"
   ```

3. **Update agent instructions** to include new capabilities

### Modifying Agent Behavior

Edit the `instruction` section in `calculator_agent.yaml` to change:
- Response style and tone
- Supported operations  
- Error handling approach
- Interaction patterns

## Contributing

When extending this calculator agent:

1. **Follow SAM patterns** for tool development
2. **Add comprehensive error handling** for edge cases
3. **Update documentation** with new capabilities  
4. **Test thoroughly** with various input types
5. **Consider security implications** of mathematical operations

## License

This calculator agent example is part of the Solace Agent Mesh project and follows the same licensing terms.