import os
from litellm import completion
from dotenv import load_dotenv
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from scripts.file_utils import create_action_file
import json


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


def add_filenames_to_action_list_and_create(agent_name, action_dictionary):
    """
    Calls create_action_file for each action in action_dictionary and adds the resulting
    filename (without extension) to each action config.

    Args:
        agent_name (str): The name of the agent
        action_dictionary (list): List of action configurations

    Returns:
        list: The updated configurations with filenames
    """
    for action in action_dictionary:
        action_name = action["name"]
        action_description = action["description"]

        # Call your existing function to create the action file
        action_file_path = create_action_file(
            agent_name=agent_name,
            action_name=action_name,
            action_description=action_description,
        )

        # Extract just the filename without extension from the path
        filename = os.path.basename(action_file_path)
        action["filename"] = filename.replace(".py", "")

    return action_dictionary


def parse_config_output(text):
    """
    Parse the output response and return a valid JSON with 'file_content' and 'configs_added' fields.
    Handles backticks if they are present in the response.

    Args:
        text (str): The output response text to parse

    Returns:
        dict: A dictionary containing 'file_content' and 'configs_added' fields
    """
    # Try to find JSON content within the response
    code_block_pattern = r"```json\s*([\s\S]*?)```"
    code_block_match = re.search(code_block_pattern, text)

    if code_block_match:
        extracted_json = code_block_match.group(1).strip()
        try:
            result = json.loads(extracted_json)
            # If "file_content" exists, return immediately
            if "file_content" in result:
                return result
        except json.JSONDecodeError:
            pass  # Fall through to the next approach

    # 2. If no code block or JSON parse above failed, attempt to find a JSON object { ... }
    json_pattern = r"({[\s\S]*})"
    json_match = re.search(json_pattern, text)

    if json_match:
        candidate_json = json_match.group(1).strip()
        try:
            result = json.loads(candidate_json)
            # Ensure file_content is present
            if "file_content" in result:
                return result
        except json.JSONDecodeError:
            pass  # Fall through to more detailed parsing

    # 3. Fallback approach:
    #    - Extract file_content from backticks or standard quotes
    #    - Optionally extract configs_added
    file_content = None
    file_content_pattern = r'"file_content"\s*:\s*(?:`{3}|")([\s\S]*?)(?:`{3}|")'
    file_match = re.search(file_content_pattern, text, re.DOTALL)
    if file_match:
        file_content = file_match.group(1).strip()

    result = {"file_content": file_content if file_content is not None else ""}

    # Look for configs_added as a JSON array if it exists
    configs_pattern = r'"configs_added"\s*:\s*(\[.*?\])'
    configs_match = re.search(configs_pattern, text, re.DOTALL)
    if configs_match:
        try:
            configs_added = json.loads(configs_match.group(1))
            result["configs_added"] = configs_added
        except json.JSONDecodeError:
            # Fallback: parse any items in quotes as strings
            items = re.findall(r'"([^"]+)"', configs_match.group(1))
            if items:
                result["configs_added"] = items

    return result


def parse_test_cases_xml(xml_string: str) -> Dict[str, Any]:
    """
    Parse test cases XML into a dictionary structure.
    Args:
        xml_string: XML string containing test cases
    Returns:
        Dictionary representation of the test cases
    """
    # First, try to extract XML content from code blocks if present
    xml_content = xml_string

    # Look for XML in code blocks (```xml ... ```)
    code_block_match = re.search(
        r"```(?:xml)?\s*([\s\S]*?)\s*```", xml_string, re.DOTALL
    )
    if code_block_match:
        xml_content = code_block_match.group(1).strip()

    # If no code block found, try to find XML tags directly
    if "<test_cases>" not in xml_content:
        xml_match = re.search(
            r"(<test_cases>[\s\S]*?</test_cases>)", xml_string, re.DOTALL
        )
        if xml_match:
            xml_content = xml_match.group(1).strip()

    # If we still don't have valid XML content with root tags, wrap it
    if not xml_content.strip().startswith("<test_cases>"):
        xml_content = f"<test_cases>{xml_content}</test_cases>"

    try:
        # Parse the XML string
        root = ET.fromstring(xml_content)

        # Initialize the result dictionary
        result = {"test_cases": []}

        # If the root is not test_cases (in case we wrapped it above), find the test_cases element
        if root.tag != "test_cases":
            test_cases_elem = root.find("test_cases")
            if test_cases_elem is not None:
                root = test_cases_elem

        # Process each agent
        for agent_elem in root.findall("agent"):
            agent_name = agent_elem.get("name")
            # Process each action within the agent
            for action_elem in agent_elem.findall("action"):
                action_name = action_elem.get("name")
                # Process each test case within the action
                for test_case_elem in action_elem.findall("test_case"):
                    test_case = {
                        "agent_name": agent_name,
                        "action_name": action_name,
                        "id": test_case_elem.get("id"),
                        "title": test_case_elem.get("title"),
                    }

                    # Extract user query
                    user_query_elem = test_case_elem.find("user_query")
                    if user_query_elem is not None and user_query_elem.text:
                        test_case["user_query"] = user_query_elem.text

                    # Extract invoke action details
                    invoke_action_elem = test_case_elem.find("invoke_action")
                    if invoke_action_elem is not None:
                        invoke_action = {}
                        agent_name_elem = invoke_action_elem.find("agent_name")
                        if agent_name_elem is not None and agent_name_elem.text:
                            invoke_action["agent_name"] = agent_name_elem.text
                        action_name_elem = invoke_action_elem.find("action_name")
                        if action_name_elem is not None and action_name_elem.text:
                            invoke_action["action_name"] = action_name_elem.text
                        test_case["invoke_action"] = invoke_action

                    # Extract expected output
                    expected_output_elem = test_case_elem.find("expected_output")
                    if expected_output_elem is not None:
                        expected_output = {}
                        status_elem = expected_output_elem.find("status")
                        if status_elem is not None and status_elem.text:
                            expected_output["status"] = status_elem.text
                        description_elem = expected_output_elem.find("description")
                        if description_elem is not None and description_elem.text:
                            expected_output["description"] = description_elem.text
                        test_case["expected_output"] = expected_output

                    # Add the test case to the result
                    result["test_cases"].append(test_case)

        return result

    except ET.ParseError as e:
        # If parsing fails, return an error message
        print(f"XML parsing error: {e}")
        return {"error": f"Failed to parse XML: {str(e)}", "test_cases": []}


def add_env_variable_if_missing(
    env_var_name: str, env_var_value: str
) -> tuple[Path, bool]:
    """
    Adds an environment variable to the .env file in the project root ONLY if it doesn't already exist.
    Preserves comments and formatting in the .env file.

    Args:
        env_var_name: Name of the environment variable (e.g., ACCUWEATHER_API_KEY)
        env_var_value: Value to set for the environment variable

    Returns:
        Tuple of (path_to_env_file, was_variable_added)

    Raises:
        FileNotFoundError: If the .env file doesn't exist in the project root
    """
    # Get the project root directory
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = current_dir.parent.parent  # Adjust this if needed

    # Path to the .env file
    env_path = project_root / ".env"

    # Check if .env file exists
    if not env_path.exists():
        raise FileNotFoundError(f"No .env file found at: {env_path}")

    # Read existing content
    with open(env_path, "r") as file:
        lines = file.readlines()

    # Check if variable already exists
    for line in lines:
        # Skip comments and empty lines when checking for variables
        if line.strip() and not line.strip().startswith("#"):
            # Split only on the first equals sign
            parts = line.split("=", 1)
            if len(parts) >= 2 and parts[0].strip() == env_var_name:
                print(f"{env_var_name} already exists in: {env_path}")
                return env_path, False

    # If we get here, the variable doesn't exist - add it
    # Add a newline if the file doesn't end with one
    if lines and not lines[-1].endswith("\n"):
        lines.append("\n")

    # Add an empty line if the file doesn't end with an empty line
    if lines and lines[-1].strip():
        lines.append("\n")

    lines.append(f"{env_var_name}={env_var_value}\n")

    # Write updated content back to file
    with open(env_path, "w") as file:
        file.writelines(lines)

    print(f"Added {env_var_name} to: {env_path}")
    return env_path, True


# # Test the function
# agent_config_content = get_agent_file("test", "agent_main")
# print(agent_config_content)

# test prompt

# prompt = create_agent_prompt("finance", "I want to build an agent that gets the stock price for a specific stock.")
# print(prompt)[{'name': 'GetCurrentWeather', 'description': 'Retrieves the current weather conditions for a specified location. The location can be provided as a city name, address, or geographic coordinates (latitude and longitude). This action connects to weather data services to obtain real-time information.', 'returns': 'A structured weather report containing: current temperature (in both Celsius and Fahrenheit), weather conditions (sunny, cloudy, rainy, etc.), humidity percentage, wind speed and direction, barometric pressure, visibility, and the local time of the weather reading.'}, {'name': 'GetForecast', 'description': 'Retrieves a weather forecast for a specified location. The user can optionally specify the forecast duration (e.g., 24-hour, 3-day, or 7-day forecast). This action provides predictive weather information to help users plan ahead.', 'returns': 'A day-by-day forecast containing predicted high and low temperatures, precipitation probability, expected weather conditions, and any weather alerts or warnings for the requested timeframe.'}]
# print(make_llm_api_call(prompt))

# Example usage
# generate_agent_component(
#     agent_name="stock_price",
#     imports=[
#         "from stock_price.actions.get_stock_price import GetStockPrice",
#         "from stock_price.actions.analyze_stock_trend import AnalyzeStockTrend",
#     ],
#     description="This agent handles financial data processing. It should be used when a user explicitly requests information about stocks or financial metrics.",
#     actions=["GetStockPrice", "AnalyzeStockTrend"],
# )

# # Create GetStockPrice action
# create_action_file(
#     agent_name="stock_price",
#     action_name="GetStockPrice",
#     action_description="Retrieves the current price of a specified stock symbol",
#     params=[
#         {
#             "name": "symbol",
#             "desc": "The stock ticker symbol (e.g., AAPL, MSFT, GOOGL)",
#             "type": "string",
#         }
#     ],
# )

# # Create AnalyzeStockTrend action
# create_action_file(
#     agent_name="stock_price",
#     action_name="AnalyzeStockTrend",
#     action_description="Analyzes the trend of a stock over a specified time period",
#     params=[
#         {
#             "name": "symbol",
#             "desc": "The stock ticker symbol (e.g., AAPL, MSFT, GOOGL)",
#             "type": "string",
#         },
#         {
#             "name": "period",
#             "desc": "Time period for analysis (e.g., '1d', '1w', '1m', '1y')",
#             "type": "string",
#         },
#     ],
# )


# content = get_agent_file("stock_price", "agent_main")
# print(content)
