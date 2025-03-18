import os
from pathlib import Path
from dotenv import load_dotenv
from litellm import completion
import os
from dotenv import load_dotenv

def get_agent_file(agent_name: str, file_type: str, action_file_name: str = None) -> str:
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
        file_path = project_root / "modules" / "agents" / agent_name / f"{agent_name}_agent_component.py"
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
    
    with open(file_path, 'r') as file:
        content = file.read()
    
    return content

def write_agent_file(agent_name: str, file_type: str, content: str, action_file_name: str = None) -> Path:
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
        file_path = project_root / "modules" / "agents" / agent_name / f"{agent_name}_agent_component.py"
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
    with open(file_path, 'w') as file:
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
    api_key = os.environ.get('LLM_SERVICE_API_KEY')
    
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
            stream=True
        )
        
        # Initialize an empty string to collect the streamed content
        collected_content = ""
        
        # Process the streaming response
        for chunk in response_stream:
            # Extract content from the delta if it exists
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
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


def update_agent_component(agent_name, new_imports=None, new_description=None, new_actions=None):
    """
    Update the agent component file with new imports, description, and actions.
    
    Args:
        agent_name (str): The name of the agent.
        new_imports (list): List of new import statements to add.
        new_description (str): New description for the agent.
        new_actions (list): List of new action definitions to add.
    
    Returns:
        str: The updated content of the agent component file.
    """

    # Get the current content of the agent component file
    current_content = get_agent_file(agent_name, "agent_main")

    # Create a modified version of the content
    lines = current_content.split("\n")
    modified_lines = []

    # Track what section we're in                                                                                                                                                                                                                                     
    in_imports = False                                                                                                                                                                                                                                                
    in_description = False                                                                                                                                                                                                                                            
    in_actions = False                                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                    
    for line in lines:                                                                                                                                                                                                                                                
        # Handle imports section                                                                                                                                                                                                                                      
        if new_imports is not None and line.startswith("from test_agent.actions"):                                                                                                                                                                                    
            # Add all new imports before the existing action import                                                                                                                                                                                                   
            for import_stmt in new_imports:                                                                                                                                                                                                                           
                modified_lines.append(import_stmt)                                                                                                                                                                                                                    
            modified_lines.append(line)  # Add the original line                                                                                                                                                                                                      
            continue                                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                    
        # Handle description section                                                                                                                                                                                                                                  
        if new_description is not None and 'info["description"]' in line:                                                                                                                                                                                             
            # Replace the description                                                                                                                                                                                                                                 
            modified_lines.append(f'info["description"] = (\n    "{new_description}"\n)')                                                                                                                                                                             
            in_description = True                                                                                                                                                                                                                                     
            continue                                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                       
        # Skip lines until we're out of the description block                                                                                                                                                                                                         
        if in_description and line.strip() == ")":                                                                                                                                                                                                                    
            in_description = False                                                                                                                                                                                                                                    
            continue                                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                    
        # Handle actions section                                                                                                                                                                                                                                      
        if new_actions is not None and line.strip() == "actions = [SampleAction]":                                                                                                                                                                                    
            # Replace the actions list                                                                                                                                                                                                                                
            actions_str = ", ".join(new_actions)                                                                                                                                                                                                                      
            modified_lines.append(f"    actions = [{actions_str}]")                                                                                                                                                                                                   
            continue                                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                    
        # Add any line that wasn't specifically modified                                                                                                                                                                                                              
        if not in_description:                                                                                                                                                                                                                                        
            modified_lines.append(line)                                                                                                                                                                                                                               
                                                                                                                                                                                                                                                                    
    updated_content = '\n'.join(modified_lines)                                                                                                                                                                                                                       
                                                                                                                                                                                                                                                                       
    # Write the updated content back to the file                                                                                                                                                                                                                      
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))                                                                                                                                                                                                    
    project_root = current_dir.parent.parent                                                                                                                                                                                                                          
    file_path = project_root / "modules" / "agents" / agent_name / f"{agent_name}_agent_component.py"                                                                                                                                                                 
                                                                                                                                                                                                                                                                    
    with open(file_path, 'w') as file:                                                                                                                                                                                                                                
        file.write(updated_content)                                                                                                                                                                                                                                   
                                                                                                                                                                                                                                                                    
    return updated_content

# # Test the function
# agent_config_content = get_agent_file("test", "agent_main")
# print(agent_config_content)

#test prompt

# prompt = create_agent_prompt("finance", "I want to build an agent that gets the stock price for a specific stock.")
# print(prompt)
# print(make_llm_api_call(prompt))

# Example usage                                                                                                                                                                                                                                                       
# update_agent_component(                                                                                                                                                                                                                                               
#     agent_name="stock_price",                                                                                                                                                                                                                                          
#     new_imports=[                                                                                                                                                                                                                                                     
#         "from stock_price.actions.new_action import NewAction",                                                                                                                                                                                                        
#         "from stock_price.actions.another_action import AnotherAction"                                                                                                                                                                                                 
#     ],                                                                                                                                                                                                                                                                
#     new_description="This agent handles financial data processing. It should be used when a user explicitly requests information about stocks or financial metrics.",                                                                                                 
#     new_actions=["SampleAction", "NewAction", "AnotherAction"]                                                                                                                                                                                                        
# )

# content = get_agent_file("stock_price", "agent_main")
# print(content)