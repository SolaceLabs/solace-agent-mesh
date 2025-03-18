import os
from pathlib import Path
from dotenv import load_dotenv
from litellm import completion
import os
from dotenv import load_dotenv

def get_agent_file(agent_name: str, file_type: str) -> str:
    """
    Get the content of an agent file based on agent name and file type.
    
    Args:
        agent_name: Name of the agent
        file_type: Type of file to retrieve ("agent_config", "agent_main", "agent_action")
    
    Returns:
        The content of the requested file as a string
    """
    
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = current_dir.parent.parent
    
    if file_type == "agent_config":
        file_path = project_root / "configs" / "agents" / f"{agent_name}.yaml"
    elif file_type == "agent_main":
        file_path = project_root / "modules" / "agents" / agent_name / f"{agent_name}_agent_component.py"
    elif file_type == "agent_action":
        file_path = project_root / "modules" / "agents" / agent_name / "actions" / "sample_action.py"
    else:
        raise ValueError(f"Unknown file type: {file_type}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r') as file:
        content = file.read()
    
    return content

def write_agent_file(agent_name: str, file_type: str, content: str) -> Path:
    """
    Write content to an agent file based on agent name and file type.
    If the file or its parent directories don't exist, raises FileNotFoundError.
    
    Args:
        agent_name: Name of the agent
        file_type: Type of file to write ("agent_config", "agent_main", "agent_action")
        content: The content to write to the file
    
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
        file_path = project_root / "modules" / "agents" / agent_name / "actions" / "sample_action.py"
    else:
        raise ValueError(f"Unknown file type: {file_type}")
    
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

1. Refining the agent description to be clear, concise, and informative for the system. The description should explain the agent's purpose, capabilities, and appropriate use cases.

2. Creating a comprehensive list of actions this agent should be able to perform. Each action should:
   - Be named in PascalCase format (e.g., GetUserData, ProcessPayment)
   - Directly relate to the agent's core functionality
   - Represent a discrete, meaningful operation

3. For each action, provide:
   - A detailed description explaining what the action does
   - Required parameters with their data types and purpose
   - Expected output format and content
   - Any constraints, limitations, or edge cases to consider
   - Example usage scenarios

4. Ensure the actions collectively cover the full range of functionality needed for the agent to fulfill its purpose.

Format your response as an XML document with the following structure:

<agent>
  <name>{agent_name}</name>
  <description>Your refined description here</description>
  
  <actions>
    <action>
      <name>ActionName1</name>
      <description>Detailed explanation of what the action does</description>
      <parameters>
        <parameter>
          <name>param1</name>
          <type>string/number/boolean/etc</type>
          <description>Description of this parameter</description>
        </parameter>
        <parameter>
          <name>param2</name>
          <type>string/number/boolean/etc</type>
          <description>Description of this parameter</description>
        </parameter>
      </parameters>
      <returns>Description of what the action returns</returns>
      <exampleUseCases>
        <useCase>Example use case 1</useCase>
        <useCase>Example use case 2</useCase>
      </exampleUseCases>
      <constraints>Any constraints or limitations to consider</constraints>
    </action>
    
    <action>
      <name>ActionName2</name>
      <description>Detailed explanation of what the action does</description>
      <parameters>
        <parameter>
          <name>param1</name>
          <type>string/number/boolean/etc</type>
          <description>Description of this parameter</description>
        </parameter>
      </parameters>
      <returns>Description of what the action returns</returns>
      <exampleUseCases>
        <useCase>Example use case 1</useCase>
      </exampleUseCases>
      <constraints>Any constraints or limitations to consider</constraints>
    </action>
  </actions>
  
  <implementationConsiderations>Any special considerations for implementing this agent</implementationConsiderations>
</agent>
"""


# # Test the function
# agent_config_content = get_agent_file("test", "agent_main")
# print(agent_config_content)

#test prompt

#prompt = create_agent_prompt("Health Expert", "I want to build an agent that provides health-related information.")
# print(prompt)
# print(make_llm_api_call(prompt))