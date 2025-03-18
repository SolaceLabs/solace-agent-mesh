import os
from pathlib import Path
from dotenv import load_dotenv
from litellm import completion
import os
from dotenv import load_dotenv
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any


def get_agent_file(
    agent_name: str, file_type: str, action_file_name: str = None
) -> str:
    """
    Get the content of an agent file based on agent name and file type.

    Args:
        agent_name: Name of the agent
        file_type: Type of file to retrieve ("agent_config", "agent_main", "agent_action")
        action_file_name: Optional name of the action file (without .py extension) when file_type is "agent_action"

    Returns:
        The content of the requested file as a string

    Raises:
        ValueError: If file_type is unknown
        FileNotFoundError: If the requested file does not exist
    """

    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = current_dir.parent.parent

    if file_type == "agent_config":
        file_path = project_root / "configs" / "agents" / f"{agent_name}.yaml"
    elif file_type == "agent_main":
        file_path = (
            project_root
            / "modules"
            / "agents"
            / agent_name
            / f"{agent_name}_agent_component.py"
        )
    elif file_type == "agent_action":
        actions_dir = project_root / "modules" / "agents" / agent_name / "actions"

        # If specific action file is provided, use it
        if action_file_name:
            file_path = actions_dir / f"{action_file_name}.py"
        else:
            # Find the first .py file that's not __init__.py
            py_files = [f for f in actions_dir.glob("*.py") if f.name != "__init__.py"]
            if not py_files:
                raise FileNotFoundError(f"No action files found in: {actions_dir}")
            file_path = py_files[0]
    else:
        raise ValueError(f"Unknown file type: {file_type}")

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r") as file:
        content = file.read()

    return content


def write_agent_file(
    agent_name: str, file_type: str, content: str, action_file_name: str = None
) -> Path:
    """
    Write content to an existing agent file based on agent name and file type.
    Will not create new files, only update existing ones.

    Args:
        agent_name: Name of the agent
        file_type: Type of file to write ("agent_config", "agent_main", "agent_action")
        content: The content to write to the file
        action_file_name: Optional name of the action file (without .py extension) when file_type is "agent_action"

    Returns:
        The path of the written file

    Raises:
        FileNotFoundError: If the file or its parent directories don't exist
        ValueError: If the file type is unknown
    """

    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = current_dir.parent.parent

    if file_type == "agent_config":
        file_path = project_root / "configs" / "agents" / f"{agent_name}.yaml"
    elif file_type == "agent_main":
        file_path = (
            project_root
            / "modules"
            / "agents"
            / agent_name
            / f"{agent_name}_agent_component.py"
        )
    elif file_type == "agent_action":
        actions_dir = project_root / "modules" / "agents" / agent_name / "actions"

        # If specific action file is provided, use it
        if action_file_name:
            file_path = actions_dir / f"{action_file_name}.py"
        else:
            # Find the first .py file that's not __init__.py
            py_files = [f for f in actions_dir.glob("*.py") if f.name != "__init__.py"]
            if not py_files:
                raise FileNotFoundError(f"No action files found in: {actions_dir}")
            file_path = py_files[0]
    else:
        raise ValueError(f"Unknown file type: {file_type}")

    # Check if file exists
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Check if parent directory exists
    if not file_path.parent.exists():
        raise FileNotFoundError(f"Directory not found: {file_path.parent}")

    # Write content to file
    with open(file_path, "w") as file:
        file.write(content)

    print(f"Written content to: {file_path}")
    return file_path


def make_llm_api_call(prompt, model="openai/claude-3-7-sonnet"):
    """
    Make a streaming completion API call using litellm.

    Args:
        prompt (str): The prompt to complete.
        model (str): The model to use for completion.

    Returns:
        str: The combined generated text from the streaming API response.
    """
    # Get API key from environment variables
    load_dotenv()
    api_key = os.environ.get("LLM_SERVICE_API_KEY")

    if not api_key:
        raise ValueError("LLM_SERVICE_API_KEY environment variable is not set")

    # Set the API key for litellm to use
    os.environ["OPENAI_API_KEY"] = api_key

    try:
        # Make the API call using litellm with streaming enabled
        response_stream = completion(
            model=model,
            messages=[{"content": prompt, "role": "user"}],
            api_base="https://lite-llm.mymaas.net/v1",
            stream=True,
        )

        # Initialize an empty string to collect the streamed content
        collected_content = ""

        # Process the streaming response
        for chunk in response_stream:
            # Extract content from the delta if it exists
            if (
                chunk.choices
                and chunk.choices[0].delta
                and chunk.choices[0].delta.content
            ):
                content_piece = chunk.choices[0].delta.content
                collected_content += content_piece

                # Debug
                print(content_piece, end="", flush=True)

        return collected_content

    except Exception as e:
        print(f"API call error: {e}")
        raise


def create_agent_prompt(agent_name, agent_description):
    return f"""
You are tasked with creating a new agent named "{agent_name}" for an AI system. This agent will be described as: "{agent_description}".

Your job is to develop this agent by:

1. Refining the agent description to be clear, concise, and informative for the system. The description should explain the agent's purpose, and capabilities.

2. Creating a list of actions this agent should be able to perform. Try to limit the amount of actions to the core functionalities. Usually agents contain 1 to 3 core actions. Each action should:
   - Be named in PascalCase format (e.g., GetUserData, ProcessPayment)
   - Directly relate to the agent's core functionality
   - Represent a discrete, meaningful operation

3. For each action, provide:
   - A detailed description explaining what the action does
   - Expected output format and content

4. Ensure the actions collectively cover the full range of functionality needed for the agent to fulfill its purpose.

Format your response as an XML document with the following structure:

<agent>
  <name>{agent_name}</name>
  <description>Your refined description here</description>
  
  <actions>
    <action>
      <name>ActionName1</name>
      <description>Detailed explanation of what the action does</description>
      <returns>Description of what the action returns</returns>
    </action>
    
    <action>
      <name>ActionName2</name>
      <description>Detailed explanation of what the action does</description>
      <returns>Description of what the action returns</returns>
    </action>
  </actions>
</agent>
"""


def generate_agent_component(agent_name, description, actions, imports=None):
    """
    Generate a complete agent component file from scratch.

    Args:
        agent_name (str): The name of the agent (snake_case)
        description (str): Description of the agent's purpose
        actions (list): List of action class names to include
        imports (list): List of import statements for the actions

    Returns:
        str: The complete content for the agent component file
    """
    # Convert agent_name to PascalCase for class name
    class_name = (
        "".join(word.capitalize() for word in agent_name.split("_")) + "AgentComponent"
    )

    # Default imports if none provided
    if imports is None:
        imports = [
            f"from {agent_name}.actions.{action.lower()} import {action}"
            for action in actions
        ]

    # Format the actions list for the file
    actions_str = ", ".join(actions)

    # Generate the complete file content
    content = f'''"""The agent component for the {agent_name}"""                                                                                                                                                                                                      
{chr(10).join(imports)}                                                                                                                                                                                                                                               
                                                                                                                                                                                                                                                                       
import os                                                                                                                                                                                                                                                             
import copy                                                                                                                                                                                                                                                           
import sys                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                    
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))                                                                                                                                                                                                               
sys.path.append(os.path.dirname(SCRIPT_DIR))                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                                    
from solace_agent_mesh.agents.base_agent_component import (                                                                                                                                                                                                           
    agent_info,                                                                                                                                                                                                                                                       
    BaseAgentComponent,                                                                                                                                                                                                                                               
)                                                                                                                                                                                                                                                                     
                                                                                                                                                                                                                                                                    
info = copy.deepcopy(agent_info)                                                                                                                                                                                                                                      
info["agent_name"] = "{agent_name}"                                                                                                                                                                                                                                   
info["class_name"] = "{class_name}"                                                                                                                                                                                                                                   
info["description"] = (                                                                                                                                                                                                                                               
    "{description}"                                                                                                                                                                                                                                                   
)                                                                                                                                                                                                                                                                     
                                                                                                                                                                                                                                                                    
class {class_name}(BaseAgentComponent):                                                                                                                                                                                                                               
    info = info                                                                                                                                                                                                                                                       
    actions = [{actions_str}]                                                                                                                                                                                                                                         
 '''

    # Write the content to the file
    write_agent_file(agent_name, "agent_main", content)

    return content


def delete_sample_action(agent_name):
    """
    Delete the sample action from the agent component file.

    Args:
        agent_name (str): The name of the agent.

    Returns:
        bool: True if the action was successfully deleted, False otherwise.
    """
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = current_dir.parent.parent
    sample_action_path = (
        project_root
        / "modules"
        / "agents"
        / agent_name
        / "actions"
        / "sample_action.py"
    )

    if sample_action_path.exists():
        os.remove(sample_action_path)
        print(f"Deleted sample action file: {sample_action_path}")
    else:
        print(f"Sample action file not found: {sample_action_path}")
        return False


def create_action_file(agent_name, action_name, action_description, params=None):
    """
    Create a new action file from scratch with the specified parameters.

    Args:
        agent_name (str): The name of the agent (snake_case)
        action_name (str): The name of the action (PascalCase)
        action_description (str): Description of what the action does
        params (list): List of parameter dictionaries with keys 'name', 'desc', and 'type'

    Returns:
        Path: The path to the created action file
    """
    # Default parameters if none provided
    if params is None:
        params = [
            {
                "name": "query",
                "desc": "The query parameter for this action",
                "type": "string",
            }
        ]

    # Convert action name to snake_case for file naming and action name
    snake_case_action = "".join(
        ["_" + c.lower() if c.isupper() else c for c in action_name]
    ).lstrip("_")

    # Generate parameters section
    params_section = ""
    for param in params:
        params_section += f"""                    {{                                                                                                                                                                                                                  
                        "name": "{param['name']}",                                                                                                                                                                                                                    
                        "desc": "{param['desc']}",                                                                                                                                                                                                                    
                        "type": "{param['type']}",                                                                                                                                                                                                                    
                    }},\n"""

    # Remove trailing comma and newline if there are parameters
    if params_section:
        params_section = params_section.rstrip(",\n") + "\n"

    # Generate the invoke method based on parameters
    invoke_params = ", ".join([f"params[\"{param['name']}\"]" for param in params])

    # Generate the do_action method signature based on parameters
    do_action_params = ", ".join([param["name"] for param in params])

    # Generate the complete file content
    content = f'''"""                                                                                                                                                                                                                                                 
{action_description}                                                                                                                                                                                                                                                  
"""
from solace_ai_connector.common.log import log

from solace_agent_mesh.common.action import Action                                                                                                                                                                                                                    
from solace_agent_mesh.common.action_response import ActionResponse
                                                                                                                                                                                                                                  
# To import from a local file, use a relative path from the {agent_name}                                                                                                                                                                                              
# For example, to load this class, use:                                                                                                                                                                                                                               
#   from {agent_name}.actions.{snake_case_action} import {action_name}                                                                                                                                                                                                
                                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                    
class {action_name}(Action):                                                                                                                                                                                                                                          
    def __init__(self, **kwargs):                                                                                                                                                                                                                                     
        super().__init__(                                                                                                                                                                                                                                            
            {{                                                                                                                                                                                                                                                        
                "name": "{snake_case_action}",                                                                                                                                                                                                                        
                "prompt_directive": "{action_description}",                                                                                                                                                                                                           
                "params": [                                                                                                                                                                                                                                           
{params_section}                ],                                                                                                                                                                                                                                    
                "required_scopes": ["{agent_name}:{snake_case_action}:read"],                                                                                                                                                                                         
            }},                                                                                                                                                                                                                                                       
            **kwargs,                                                                                                                                                                                                                                                 
        )                                                                                                                                                                                                                                                             
                                                                                                                                                                                                                                                                    
    def invoke(self, params, meta={{}}):                                                                                                                                                                                                                              
        log.debug("Executing {action_name} with parameters: %s", params)                                                                                                                                                                                              
        return self.do_action({invoke_params})                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                    
    def do_action(self, {do_action_params}) -> ActionResponse:                                                                                                                                                                                                        
        # Implement your action logic here                                                                                                                                                                                                                            
        result = f"Processed {do_action_params} successfully"                                                                                                                                                                                                         
        return ActionResponse(message=result)                                                                                                                                                                                                                         
'''

    # Create the new action file
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = current_dir.parent.parent
    action_file_path = (
        project_root
        / "modules"
        / "agents"
        / agent_name
        / "actions"
        / f"{snake_case_action}.py"
    )

    # Create directory if it doesn't exist
    action_file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(action_file_path, "w") as file:
        file.write(content)

    print(f"Created action file: {action_file_path}")
    return action_file_path



def parse_actions_from_global_context(xml_string: str) -> List[Dict[str, Any]]:
    """
    Parse XML output from LLM to extract action details.
    
    Args:
        xml_string: XML string from LLM
    
    Returns:
        List of dictionaries with action details
    """
    # Extract the XML content from the code block
    match = re.search(r'```xml\n(.*?)\n```', xml_string, re.DOTALL)
    if match:
        xml_content = match.group(1)
    else:
        xml_content = xml_string
    
    # Parse the XML
    root = ET.fromstring(xml_content)
    
    # Find all actions
    actions = []
    for action_elem in root.findall('./actions/action'):
        action = {
            'name': action_elem.find('name').text if action_elem.find('name') is not None else '',
            'description': action_elem.find('description').text if action_elem.find('description') is not None else '',
            'returns': action_elem.find('returns').text if action_elem.find('returns') is not None else ''
        }
        actions.append(action)
    
    return actions


# # Test the function
# agent_config_content = get_agent_file("test", "agent_main")
# print(agent_config_content)

# test prompt

# prompt = create_agent_prompt("finance", "I want to build an agent that gets the stock price for a specific stock.")
# print(prompt)
# print(make_llm_api_call(prompt))

# Example usage
generate_agent_component(
    agent_name="stock_price",
    imports=[
        "from stock_price.actions.get_stock_price import GetStockPrice",
        "from stock_price.actions.analyze_stock_trend import AnalyzeStockTrend",
    ],
    description="This agent handles financial data processing. It should be used when a user explicitly requests information about stocks or financial metrics.",
    actions=["GetStockPrice", "AnalyzeStockTrend"],
)

# Create GetStockPrice action
create_action_file(
    agent_name="stock_price",
    action_name="GetStockPrice",
    action_description="Retrieves the current price of a specified stock symbol",
    params=[
        {
            "name": "symbol",
            "desc": "The stock ticker symbol (e.g., AAPL, MSFT, GOOGL)",
            "type": "string",
        }
    ],
)

# Create AnalyzeStockTrend action
create_action_file(
    agent_name="stock_price",
    action_name="AnalyzeStockTrend",
    action_description="Analyzes the trend of a stock over a specified time period",
    params=[
        {
            "name": "symbol",
            "desc": "The stock ticker symbol (e.g., AAPL, MSFT, GOOGL)",
            "type": "string",
        },
        {
            "name": "period",
            "desc": "Time period for analysis (e.g., '1d', '1w', '1m', '1y')",
            "type": "string",
        },
    ],
)


# content = get_agent_file("stock_price", "agent_main")
# print(content)
