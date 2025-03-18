import os
from pathlib import Path
from dotenv import load_dotenv
import requests
import json

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

def make_llm_api_call(prompt, model="claude-3-7-sonnet"):
    """
    Make a completion API call to the local server.
    
    Args:
        prompt (str): The prompt to complete.
        model (str): The model to use for completion.
        
    Returns:
        dict: The API response as a dictionary.
    """
    # Get API key from environment variables
    load_dotenv()
    api_key = os.environ.get('LLM_SERVICE_API_KEY')
    
    if not api_key:
        raise ValueError("API_KEY environment variable is not set")
    
    # API endpoint
    url = 'https://lite-llm.mymaas.net/completions'
    
    # Headers
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    # Request payload
    payload = {
        'model': model,
        'prompt': prompt,
    }
    
    # Make the POST request
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    # Check if the request was successful
    if response.status_code == 200:
        return response.json()['choices'][0]['text']
    else:
        raise Exception(f"API call failed with status code {response.status_code}: {response.text}")



# # Test the function
# agent_config_content = get_agent_file("test", "agent_config")
# print(agent_config_content)