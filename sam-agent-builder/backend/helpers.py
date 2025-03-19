import os
from litellm import completion
from dotenv import load_dotenv
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List, Dict, Any


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


def parse_agent_from_global_context(xml_string: str) -> Dict[str, Any]:
    """
    Parse XML output from LLM to extract agent details.

    Args:
        xml_string: XML string from LLM

    Returns:
        Dictionary with agent details
    """
    # Extract the XML content from the code block
    match = re.search(r"```xml\n(.*?)\n```", xml_string, re.DOTALL)
    if match:
        xml_content = match.group(1)
    else:
        xml_content = xml_string

    # Parse the XML
    root = ET.fromstring(xml_content)

    # Extract agent details
    agent = {
        "name": root.find("name").text,
        "description": root.find("description").text,
        "actions": [],
    }

    return agent


def parse_actions_from_global_context(xml_string: str) -> List[Dict[str, Any]]:
    """
    Parse XML output from LLM to extract action details.

    Args:
        xml_string: XML string from LLM

    Returns:
        List of dictionaries with action details
    """
    # Extract the XML content from the code block
    match = re.search(r"```xml\n(.*?)\n```", xml_string, re.DOTALL)
    if match:
        xml_content = match.group(1)
    else:
        xml_content = xml_string

    # Parse the XML
    root = ET.fromstring(xml_content)

    # Find all actions
    actions = []
    for action_elem in root.findall("./actions/action"):
        action = {
            "name": (
                action_elem.find("name").text
                if action_elem.find("name") is not None
                else ""
            ),
            "description": (
                action_elem.find("description").text
                if action_elem.find("description") is not None
                else ""
            ),
            "parameters": [
                {
                    "name": param.find("name").text,
                    "type": param.find("type").text,
                    "desc": param.find("description").text,
                }
                for param in action_elem.findall("parameters/parameter")
            ],
            "returns": (
                action_elem.find("returns").text
                if action_elem.find("returns") is not None
                else ""
            ),
        }
        actions.append(action)

    return actions


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
